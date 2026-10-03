import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.backend.db import (
    Customer,
    Order,
    OrderItem,
    PolicyDoc,
    Product,
    SupportTicket,
    get_engine,
    get_session_factory,
    init_db,
)
from src.backend.repositories import (
    create_support_ticket as repo_create_ticket,
    execute_cancel_order as repo_cancel_order,
    execute_create_refund as repo_create_refund,
    execute_create_return as repo_create_return,
    get_customer as repo_get_customer,
    get_customer_conversations as repo_get_conversations,
    get_customer_tickets as repo_get_tickets,
    get_order as repo_get_order,
    get_order_items as repo_get_items,
    get_product as repo_get_product,
    get_product_reviews as repo_get_product_reviews,
    get_product_specs as repo_get_product_specs,
    normalize_customer_id,
    normalize_order_id,
    verify_order_ownership,
)
from src.policy.engine import (
    calculate_refund_amount as policy_calc_refund,
    check_cancellation_eligibility as policy_check_cancellation,
    check_refund_eligibility as policy_check_refund,
    check_return_eligibility as policy_check_return,
    check_warranty_eligibility as policy_check_warranty,
    get_applicable_policy as policy_get_applicable,
)
from src.risk.engine import detect_risk_signals as risk_detect

logger = logging.getLogger("support_agent.tools")

_engine = get_engine()
init_db(_engine)
_SessionLocal = get_session_factory(_engine)


def configure_db(engine) -> None:
    """Point tools at a different engine (used by tests)."""
    global _engine, _SessionLocal
    _engine = engine
    init_db(_engine)
    _SessionLocal = get_session_factory(_engine)


def _session():
    return _SessionLocal()


# ==========================================
# 1. READ / LOOKUP TOOLS
# ==========================================

def get_customer(identifier: str) -> dict:
    """Fetch customer profile by customer_id or email."""
    with _session() as s:
        cust = repo_get_customer(s, identifier)
        if not cust:
            return {"error": f"Customer '{identifier}' not found."}
        return {
            "customer_id": cust.customer_id,
            "name": f"{cust.first_name} {cust.last_name}",
            "email": cust.email,
            "phone": cust.phone,
            "city": cust.city,
            "state": cust.state,
            "customer_since": cust.customer_since,
            "loyalty_tier": cust.loyalty_tier,
            "account_status": cust.account_status,
            "total_orders": cust.total_orders,
            "total_spend": cust.total_spend,
            "preferred_language": cust.preferred_language,
        }


def get_order(order_id: str | int) -> dict:
    """Retrieve full details of an order including status, dates, delivery, and payment info."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"Order '{order_id}' not found."}
        return {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "order_date": order.order_date,
            "order_status": order.order_status,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "subtotal": order.subtotal,
            "discount": order.discount,
            "shipping_fee": order.shipping_fee,
            "tax": order.tax,
            "total_amount": order.total_amount,
            "city": order.city,
            "state": order.state,
            "estimated_delivery_date": order.estimated_delivery_date,
            "actual_delivery_date": order.actual_delivery_date,
            "tracking_number": order.tracking_number,
            "courier": order.courier,
            "delivery_status": order.delivery_status,
            "delivery_otp_verified": order.delivery_otp_verified,
            "cancellation_status": order.cancellation_status,
            "refund_status": order.refund_status,
        }


def get_order_status(order_id: str | int) -> dict:
    """Look up the current status (placed/shipped/delivered/cancelled) of an order."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"No order found with id {order_id}"}
        return {"order_id": order.order_id, "status": order.order_status}


def get_order_details(order_id: str | int) -> dict:
    """Get full details of an order: customer, items, status, date, amount."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"No order found with id {order_id}"}
        cust = repo_get_customer(s, order.customer_id)
        items = repo_get_items(s, order.order_id)
        item_names = []
        for it in items:
            p = repo_get_product(s, it.product_id)
            item_names.append(p.product_name if p else it.product_id)
        item_summary = ", ".join(item_names) if item_names else "Order Items"

        return {
            "order_id": order.order_id,
            "customer_name": f"{cust.first_name} {cust.last_name}" if cust else order.customer_id,
            "item": item_summary,
            "status": order.order_status,
            "order_date": order.order_date,
            "amount": order.total_amount,
        }


def track_shipment(order_id: str | int) -> dict:
    """Get shipment tracking info for an order based on its current status."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"No order found with id {order_id}"}
        
        status = order.order_status
        messages = {
            "placed": "Order placed, not yet handed to courier.",
            "confirmed": "Order confirmed, preparing for dispatch.",
            "processing": "Order in processing at the fulfillment centre.",
            "shipped": f"In transit with {order.courier or 'courier'} (Tracking: {order.tracking_number or 'N/A'}).",
            "out_for_delivery": f"Out for delivery today with {order.courier or 'courier'}.",
            "delivered": f"Delivered on {order.actual_delivery_date or 'recent date'}.",
            "cancelled": "Order was cancelled; no shipment in progress.",
            "returned": "Order was returned to warehouse.",
        }
        msg = messages.get(status, f"Order status is {status}.")
        return {
            "order_id": order.order_id,
            "status": status,
            "courier": order.courier,
            "tracking_number": order.tracking_number,
            "estimated_delivery_date": order.estimated_delivery_date,
            "actual_delivery_date": order.actual_delivery_date,
            "tracking_message": msg,
        }


def get_order_items(order_id: str | int) -> list:
    """List all line items for an order, including product details, price, and quantities."""
    with _session() as s:
        items = repo_get_items(s, order_id)
        result = []
        for it in items:
            prod = repo_get_product(s, it.product_id)
            result.append({
                "order_item_id": it.order_item_id,
                "order_id": it.order_id,
                "product_id": it.product_id,
                "product_name": prod.product_name if prod else "Unknown",
                "category": prod.category if prod else "",
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "discount": it.discount,
                "final_price": it.final_price,
                "item_status": it.item_status,
                "return_status": it.return_status,
                "returnable": prod.returnable if prod else True,
                "replacement_available": prod.replacement_available if prod else True,
            })
        return result


def get_product(product_id_or_sku: str) -> dict:
    """Fetch product specifications, category, returnability, and warranty duration."""
    with _session() as s:
        prod = repo_get_product(s, product_id_or_sku)
        if not prod:
            return {"error": f"Product '{product_id_or_sku}' not found."}
        return {
            "product_id": prod.product_id,
            "sku": prod.sku,
            "product_name": prod.product_name,
            "category": prod.category,
            "subcategory": prod.subcategory,
            "brand": prod.brand,
            "description": prod.description,
            "price": prod.price,
            "mrp": prod.mrp,
            "discount_percent": prod.discount_percent,
            "stock_quantity": prod.stock_quantity,
            "warranty_months": prod.warranty_months,
            "returnable": prod.returnable,
            "replacement_available": prod.replacement_available,
            "rating": prod.rating,
            "review_count": prod.review_count,
        }


def get_product_specs(product_id_or_sku: str) -> dict:
    """Retrieve authoritative technical specifications and markdown spec sheet for a product.

    Verifies product exists, returns exact markdown specifications, and never fabricates values.
    Returns 'specification unavailable' if no matching spec sheet exists.
    """
    with _session() as s:
        prod = repo_get_product(s, product_id_or_sku)
        if not prod:
            return {"found": False, "error": f"Product '{product_id_or_sku}' not found."}

        spec_text = repo_get_product_specs(s, prod.product_id)
        if not spec_text:
            return {
                "found": True,
                "product_id": prod.product_id,
                "product_name": prod.product_name,
                "category": prod.category,
                "specifications": "specification unavailable",
            }

        return {
            "found": True,
            "product_id": prod.product_id,
            "product_name": prod.product_name,
            "category": prod.category,
            "specifications": spec_text,
        }


def get_product_reviews(product_id_or_sku: str, limit: int = 5) -> dict:
    """Fetch verified customer reviews, ratings, and sentiment for a product from authoritative review records."""
    with _session() as s:
        prod = repo_get_product(s, product_id_or_sku)
        if not prod:
            return {"found": False, "error": f"Product '{product_id_or_sku}' not found."}
        reviews = repo_get_product_reviews(s, prod.product_id, limit=limit)
        return {
            "found": True,
            "product_id": prod.product_id,
            "product_name": prod.product_name,
            "average_rating": prod.rating,
            "total_reviews": prod.review_count,
            "reviews": [
                {
                    "review_id": r.review_id,
                    "customer_id": r.customer_id,
                    "reviewer_name": f"Customer {r.customer_id}",
                    "rating": r.rating,
                    "title": r.title,
                    "review_text": r.review_text,
                    "review_date": r.review_date,
                    "verified_purchase": r.verified_purchase,
                    "helpful_votes": r.helpful_votes,
                }
                for r in reviews
            ],
        }


def get_conversations(customer_id: str) -> list:
    """Pull previous conversation history for a customer to maintain continuity."""
    with _session() as s:
        convs = repo_get_conversations(s, customer_id)
        result = []
        for c in convs[:5]:  # Return latest 5 conversations
            import json
            msgs = []
            try:
                msgs = json.loads(c.messages_json)
            except Exception:
                pass
            result.append({
                "conversation_id": c.conversation_id,
                "started_at": c.started_at,
                "channel": c.channel,
                "status": c.status,
                "order_id": c.order_id,
                "ticket_id": c.ticket_id,
                "messages": msgs,
            })
        return result


def get_support_tickets(customer_id: str) -> list:
    """Retrieve all support tickets for a customer."""
    with _session() as s:
        tickets = repo_get_tickets(s, customer_id)
        return [
            {
                "ticket_id": t.ticket_id,
                "order_id": t.order_id,
                "created_at": t.created_at,
                "category": t.category,
                "subcategory": t.subcategory,
                "priority": t.priority,
                "status": t.status,
                "assigned_team": t.assigned_team,
                "issue_summary": t.issue_summary,
                "resolution": t.resolution,
            }
            for t in tickets
        ]


# ==========================================
# 2. VERIFICATION & POLICY CHECK TOOLS
# ==========================================

def get_applicable_policy(policy_type: str, order_id_or_date: str) -> dict:
    """Get the versioned policy applicable for a given order placement date."""
    with _session() as s:
        order = repo_get_order(s, order_id_or_date)
        order_date = order.order_date if order else order_id_or_date
        return policy_get_applicable(policy_type, order_date)


def check_refund_eligibility(
    order_id: str | int,
    reason: str = "change_of_mind",
    order_item_id: Optional[str] = None,
    current_date: Optional[str] = None,
) -> dict:
    """Check whether an order or item is eligible for a refund under the applicable policy version."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"eligible": False, "error": f"No order found with id {order_id}"}
        cust = repo_get_customer(s, order.customer_id)
        
        items = repo_get_items(s, order.order_id)
        target_item = None
        if order_item_id:
            target_item = next((it for it in items if it.order_item_id == order_item_id), None)
        elif items:
            target_item = items[0]

        prod = repo_get_product(s, target_item.product_id) if target_item else None

        res = policy_check_refund(
            order=order,
            customer=cust,
            item=target_item,
            product=prod,
            reason=reason,
            current_date_val=current_date,
        )

        return {
            "order_id": order.order_id,
            "eligible": res.eligible,
            "reason": res.reason,
            "reason_code": res.reason_code,
            "policy_version": res.policy_version,
            "max_refund_amount": float(res.max_refund_amount),
            "item_refund_amount": float(res.item_refund_amount),
            "restocking_fee": float(res.restocking_fee),
            "requires_human_approval": res.requires_human_approval,
            "escalation_team": res.escalation_team,
            "risk_flags": res.risk_flags,
        }


def calculate_refund(
    order_id: str | int,
    reason: str = "change_of_mind",
    order_item_id: Optional[str] = None,
) -> dict:
    """Independently calculate the exact deterministic refund amount (price + 18% GST - restocking fee)."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"Order {order_id} not found."}
        items = repo_get_items(s, order.order_id)
        target_item = None
        if order_item_id:
            target_item = next((it for it in items if it.order_item_id == order_item_id), None)
        elif items:
            target_item = items[0]
        prod = repo_get_product(s, target_item.product_id) if target_item else None

        return policy_calc_refund(order, target_item, prod, reason)


def check_return_eligibility(
    order_id: str | int,
    reason: str = "change_of_mind",
    order_item_id: Optional[str] = None,
    current_date: Optional[str] = None,
) -> dict:
    """Check whether a product can be returned based on category returnability and delivery window."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"eligible": False, "error": f"Order {order_id} not found."}
        cust = repo_get_customer(s, order.customer_id)
        items = repo_get_items(s, order.order_id)
        target_item = next((it for it in items if it.order_item_id == order_item_id), items[0] if items else None)
        prod = repo_get_product(s, target_item.product_id) if target_item else None

        res = policy_check_return(
            order=order,
            customer=cust,
            item=target_item,
            product=prod,
            reason=reason,
            current_date_val=current_date,
        )
        return {
            "order_id": order.order_id,
            "eligible": res.eligible,
            "reason": res.reason,
            "reason_code": res.reason_code,
            "policy_version": res.policy_version,
            "window_days": res.window_days,
            "days_since_delivery": res.days_since_delivery,
            "requires_human_approval": res.requires_human_approval,
            "remedy": res.remedy,
            "escalation_team": res.escalation_team,
        }


def check_warranty_eligibility(
    order_id: str | int,
    issue_description: str,
    product_id: Optional[str] = None,
    current_date: Optional[str] = None,
) -> dict:
    """Check whether an item is covered under manufacturer warranty vs expired vs physical damage."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        items = repo_get_items(s, order.order_id) if order else []
        prod = None
        if product_id:
            prod = repo_get_product(s, product_id)
        elif items:
            prod = repo_get_product(s, items[0].product_id)

        if not prod:
            return {"eligible": False, "error": "Product could not be identified."}

        res = policy_check_warranty(prod, order, issue_description, current_date)
        return {
            "eligible": res.eligible,
            "status": res.status,
            "reason": res.reason,
            "warranty_months": res.warranty_months,
            "expiry_date": res.expiry_date,
            "days_remaining": res.days_remaining,
            "remedy": res.remedy,
            "requires_human": res.requires_human,
        }


def check_cancellation_eligibility(order_id: str | int) -> dict:
    """Validate whether an order is in a cancellable stage before shipping."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"eligible": False, "error": f"Order {order_id} not found."}
        cust = repo_get_customer(s, order.customer_id)
        res = policy_check_cancellation(order, cust)
        return {
            "order_id": order.order_id,
            "eligible": res.eligible,
            "reason": res.reason,
            "order_status": res.order_status,
            "refund_applicable": res.refund_applicable,
            "refund_amount": float(res.refund_amount),
        }


def check_delivery_claim(
    order_id: str | int,
    customer_statement: str,
) -> dict:
    """Verify customer delivery claims against authoritative tracking, OTP records, and delivery status."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"verified": False, "error": f"Order {order_id} not found."}

        is_delivered = order.delivery_status == "delivered" or order.order_status == "delivered"
        has_otp = bool(order.delivery_otp_verified)

        statement_lower = customer_statement.lower()
        claims_not_delivered = any(p in statement_lower for p in ["not received", "never received", "didn't receive", "not delivered", "haven't received"])

        if is_delivered and has_otp and claims_not_delivered:
            return {
                "verified": False,
                "contradiction": True,
                "delivery_status": "delivered",
                "delivery_otp_verified": True,
                "actual_delivery_date": order.actual_delivery_date,
                "action": "ESCALATE",
                "escalation_team": "Logistics Desk",
                "message": (
                    f"Our records show order {order.order_id} was delivered and OTP-verified on {order.actual_delivery_date}. "
                    "Per NovaMart policy, OTP-confirmed deliveries cannot be refunded automatically. "
                    "This case is being escalated to the Logistics Desk for investigation."
                ),
            }
        elif is_delivered and not has_otp and claims_not_delivered:
            return {
                "verified": False,
                "contradiction": False,
                "delivery_status": "delivered",
                "delivery_otp_verified": False,
                "action": "INVESTIGATE",
                "escalation_team": "Logistics Desk",
                "message": (
                    f"Order {order.order_id} is marked delivered without OTP. A delivery investigation has been logged with {order.courier or 'the courier'}."
                ),
            }
        else:
            return {
                "verified": True,
                "contradiction": False,
                "delivery_status": order.delivery_status,
                "actual_delivery_date": order.actual_delivery_date,
                "estimated_delivery_date": order.estimated_delivery_date,
                "tracking_number": order.tracking_number,
                "courier": order.courier,
                "action": "ANSWER",
            }


def check_payment_status(order_id: str | int) -> dict:
    """Look up the payment status (pending/paid/refunded) and method for an order."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"No order found with id {order_id}"}
        return {
            "order_id": order.order_id,
            "status": order.payment_status,
            "method": order.payment_method,
            "amount": order.total_amount,
        }


def get_payment_status(order_id: str | int) -> dict:
    """Backward-compatible payment status lookup."""
    return check_payment_status(order_id)


def process_payment(order_id: str | int, method: str) -> dict:
    """Process a pending payment for an order using the given method."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"error": f"No payment found for order {order_id}"}
        if order.payment_status == "paid":
            return {"success": False, "order_id": order.order_id, "reason": "Payment is already paid."}
        if order.payment_status == "refunded":
            return {"success": False, "order_id": order.order_id, "reason": "Payment was refunded; cannot reprocess."}

        order.payment_status = "paid"
        order.payment_method = method
        s.commit()
        return {"success": True, "order_id": order.order_id, "status": "paid", "method": method}


def verify_customer_order_ownership(customer_id: str, order_id: str | int) -> bool:
    """Ensure that the order belongs to the customer before exposing details or modifying state."""
    with _session() as s:
        return verify_order_ownership(s, customer_id, order_id)


def detect_risk_signals(
    customer_message: str,
    customer_id: Optional[str] = None,
    order_id: Optional[str | int] = None,
    requested_amount: Optional[float] = None,
) -> dict:
    """Detect safety, legal, contradiction, or threshold risk signals."""
    with _session() as s:
        cust = repo_get_customer(s, customer_id) if customer_id else None
        order = repo_get_order(s, order_id) if order_id else None
        tickets = repo_get_tickets(s, cust.customer_id) if cust else []
        res = risk_detect(
            customer_message=customer_message,
            customer=cust,
            order=order,
            recent_tickets=tickets,
            requested_amount=requested_amount,
            target_customer_id=normalize_customer_id(customer_id) if customer_id else None,
        )
        return {
            "risk_level": res.risk_level,
            "signals": res.signals,
            "requires_escalation": res.requires_escalation,
            "escalation_team": res.escalation_team,
            "escalation_reason": res.escalation_reason,
        }


# ==========================================
# 3. ACTION / MUTATION TOOLS (Never blind)
# ==========================================

def create_refund(
    order_id: str | int,
    amount: float,
    reason: str,
    customer_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    current_date: Optional[str] = None,
) -> dict:
    """Issue a verified refund. Re-checks ownership, eligibility, and caps independently."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"success": False, "error": f"Order {order_id} does not exist."}

        # Idempotency early-exit check
        if idempotency_key:
            from src.backend.db import RefundRecord
            existing = s.query(RefundRecord).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return {
                    "success": True,
                    "refund_id": existing.refund_id,
                    "order_id": order.order_id,
                    "amount": existing.amount,
                    "status": existing.status,
                    "idempotent": True,
                    "verified": True,
                }

        # Ownership verification
        if customer_id and not verify_order_ownership(s, customer_id, order.order_id):
            return {"success": False, "error": "Authorization failed: Order does not belong to customer."}

        # Policy & eligibility re-verification
        eligibility = check_refund_eligibility(order.order_id, reason, order_item_id, current_date=current_date)
        if not eligibility["eligible"]:
            return {"success": False, "reason": eligibility["reason"], "error": "Order not eligible for refund"}

        # Human approval threshold check
        if eligibility["requires_human_approval"]:
            return {
                "success": False,
                "escalated": True,
                "reason": f"Order total exceeds approval threshold ({eligibility['policy_version']}). Escalating for human authorization.",
                "escalation_team": eligibility["escalation_team"] or "Refunds & Payments",
            }

        # Cap verification: amount cannot exceed authorized amount
        authorized_max = eligibility["max_refund_amount"]
        if amount > authorized_max:
            amount = authorized_max  # Silently cap to authorized maximum

        # Execute mutation with idempotency
        res = repo_create_refund(
            session=s,
            order_id=order.order_id,
            amount=amount,
            reason=reason,
            policy_version=eligibility["policy_version"],
            order_item_id=order_item_id,
            idempotency_key=idempotency_key,
        )

        # POST-MUTATION VERIFICATION: verify from DB
        verified_order = repo_get_order(s, order.order_id)
        if verified_order.refund_status != "requested":
            return {"success": False, "error": "Post-mutation verification failed."}

        res["verified"] = True
        return res


def initiate_refund(
    order_id: str | int,
    reason: str,
    current_date: Optional[str] = None,
) -> dict:
    """Backward-compatible refund initiation."""
    calc = calculate_refund(order_id, reason)
    amount = calc.get("net_refund_amount", 0.0)
    return create_refund(order_id=order_id, amount=amount, reason=reason, current_date=current_date)


def create_return(
    order_id: str | int,
    reason: str,
    customer_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Initiate a verified return request. Re-verifies category returnability and window before mutating."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"success": False, "error": f"Order {order_id} does not exist."}

        # Idempotency early-exit check
        if idempotency_key:
            from src.backend.db import ReturnRecord
            existing = s.query(ReturnRecord).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return {
                    "success": True,
                    "return_id": existing.return_id,
                    "order_id": order.order_id,
                    "status": existing.status,
                    "idempotent": True,
                    "verified": True,
                }

        if customer_id and not verify_order_ownership(s, customer_id, order.order_id):
            return {"success": False, "error": "Authorization failed: Order does not belong to customer."}

        ret_check = check_return_eligibility(order.order_id, reason, order_item_id)
        if not ret_check["eligible"]:
            return {"success": False, "reason": ret_check["reason"], "error": "Item not eligible for return"}

        if ret_check["requires_human_approval"]:
            return {
                "success": False,
                "escalated": True,
                "reason": f"Order total exceeds approval threshold ({ret_check['policy_version']}). Escalating for human authorization.",
                "escalation_team": ret_check["escalation_team"] or "Refunds & Payments",
            }

        res = repo_create_return(
            session=s,
            order_id=order.order_id,
            reason=reason,
            order_item_id=order_item_id,
            idempotency_key=idempotency_key,
        )

        res["verified"] = True
        return res


def cancel_order(
    order_id: str | int,
    customer_id: Optional[str] = None,
    reason: str = "Customer requested cancellation",
) -> dict:
    """Cancel an eligible order before shipping and process full refund if prepaid."""
    with _session() as s:
        order = repo_get_order(s, order_id)
        if not order:
            return {"success": False, "error": f"Order {order_id} does not exist."}

        if customer_id and not verify_order_ownership(s, customer_id, order.order_id):
            return {"success": False, "error": "Authorization failed: Order does not belong to customer."}

        canc_check = check_cancellation_eligibility(order.order_id)
        if not canc_check["eligible"]:
            return {"success": False, "reason": canc_check["reason"], "error": "Order cannot be cancelled"}

        res = repo_cancel_order(s, order.order_id, reason)
        
        # Verify in DB
        verified_order = repo_get_order(s, order.order_id)
        if verified_order.order_status != "cancelled":
            return {"success": False, "error": "Post-mutation verification failed."}

        res["verified"] = True
        return res


def create_support_ticket(
    customer_id: str,
    category: str,
    subcategory: str,
    issue_summary: str,
    order_id: Optional[str | int] = None,
    priority: str = "medium",
    assigned_team: str = "Tier 1 Support",
) -> dict:
    """Create a support ticket for follow-up or escalation."""
    with _session() as s:
        t = repo_create_ticket(
            session=s,
            customer_id=customer_id,
            category=category,
            subcategory=subcategory,
            issue_summary=issue_summary,
            order_id=str(order_id) if order_id else None,
            priority=priority,
            assigned_team=assigned_team,
        )
        return {
            "ticket_id": t.ticket_id,
            "status": t.status,
            "assigned_team": t.assigned_team,
            "created_at": t.created_at,
        }


def escalate_to_human(
    reason: str,
    context: str,
    customer_id: Optional[str] = None,
    order_id: Optional[str | int] = None,
    team: str = "Customer Experience",
    priority: str = "medium",
) -> dict:
    """Escalate a request to human agents by creating a support ticket and returning clear next steps."""
    cid = customer_id or "CUST-00001"
    ticket_info = create_support_ticket(
        customer_id=cid,
        category="escalation",
        subcategory="agent_handoff",
        issue_summary=f"Escalation: {reason} | Context: {context}",
        order_id=order_id,
        priority=priority,
        assigned_team=team,
    )
    ticket_id = ticket_info["ticket_id"]
    logger.warning("ESCALATION ticket=%s team=%s reason=%s", ticket_id, team, reason)
    return {
        "escalated": True,
        "ticket_id": ticket_id,
        "assigned_team": team,
        "reason": reason,
        "message": f"This has been escalated to our {team} specialist (ticket #{ticket_id}). They will investigate and follow up with you.",
    }


# ==========================================
# 4. POLICY / FAQ RETRIEVAL
# ==========================================

_POLICY_CACHE = {}


def answer_faq(question: str) -> str:
    """Answer a general policy question (shipping, returns, cancellations, refunds, contact info) from official policy docs."""
    q = question.lower()
    if "shipping" in q or "delivery" in q:
        return "NovaMart standard delivery takes 3-5 business days in metro areas. Orders above ₹1,000 get free shipping; otherwise flat ₹79 applies. Orders above ₹5,000 require OTP verification."
    if "return" in q:
        return "NovaMart allows returns within the policy window from delivery (10 days under v1 / 7 days under v2 for change of mind). Gold loyalty members get +2 days, Platinum members get +3 days. Products must be unused in original packaging."
    if "cancel" in q:
        return "Orders can be cancelled free of charge before shipment (while in placed, confirmed, or processing stage). Once shipped, delivery can be refused at door."
    if "refund" in q:
        return "Refunds are issued to the original payment method. They include the item price plus 18% GST. Processing takes 1-3 business days for UPI, instant for wallet, and 5-7 business days for cards."
    if "contact" in q or "email" in q:
        return "You can reach NovaMart support at support@novamart.example or raise a support ticket in this chat."

    return (
        "I don't have a specific policy answer for that. "
        "You can reach human support at support@example.com for more detail."
    )
