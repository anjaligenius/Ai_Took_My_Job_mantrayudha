import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta

from src.policy.models import (
    CancellationEligibilityResult,
    PolicyRuleSet,
    RefundEligibilityResult,
    ReturnEligibilityResult,
    WarrantyEligibilityResult,
)
from src.policy.rules import REFUND_RETURN_V1, REFUND_RETURN_V2

logger = logging.getLogger("support_agent.policy_engine")

V2_CUTOFF_DATE = date(2026, 6, 1)

RESTOCKING_CATEGORIES = {"laptops", "tablets", "cameras", "monitors"}
PHYSICAL_DAMAGE_KEYWORDS = ["dropped", "crack", "cracked", "broken screen", "liquid", "water", "spill", "physical"]
SAFETY_KEYWORDS = ["swelling", "swollen", "bulge", "bulging", "smoke", "spark", "explosion", "burned", "fire", "overheating"]


def parse_date(date_val: str | date | datetime | None) -> Optional[date]:
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    s = str(date_val).strip()
    if not s:
        return None
    # If string contains space or T, take date part
    s_date = s.split(" ")[0].split("T")[0]
    try:
        return datetime.strptime(s_date, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_rule_set_for_order(order_date_val: str | date | datetime | None) -> PolicyRuleSet:
    dt = parse_date(order_date_val)
    if not dt or dt < V2_CUTOFF_DATE:
        return REFUND_RETURN_V1
    return REFUND_RETURN_V2


def get_applicable_policy(policy_type: str, order_date_val: str | date | datetime | None) -> dict:
    rules = get_rule_set_for_order(order_date_val)
    return {
        "policy_type": policy_type,
        "version": rules.version,
        "effective_from": rules.effective_from,
        "effective_to": rules.effective_to,
        "rules": {
            "change_of_mind_window_days": rules.change_of_mind_window_days,
            "defect_window_days": rules.defect_window_days,
            "approval_threshold": float(rules.approval_threshold),
            "restocking_fee_rate": float(rules.restocking_fee_rate),
            "restocking_fee_cap": float(rules.restocking_fee_cap),
            "restocking_categories": rules.restocking_categories,
            "loyalty_extensions": rules.loyalty_extensions,
        },
    }


def check_refund_eligibility(
    order,
    customer=None,
    item=None,
    product=None,
    reason: str = "defective",
    current_date_val: str | date | None = None,
    previous_ticket_date_val: str | date | None = None,
    current_date: str | date | None = None,
    **kwargs,
) -> RefundEligibilityResult:
    target_curr_date = current_date or current_date_val

    if isinstance(order, str):
        from src.tools import _session
        from src.backend.repositories import get_order, get_order_items, get_product, get_customer
        with _session() as s:
            order_obj = get_order(s, order)
            if not order_obj:
                return RefundEligibilityResult(
                    eligible=False,
                    reason=f"Order {order} not found.",
                    policy_version="v2",
                    reason_code="ORDER_NOT_FOUND",
                )
            order = order_obj
            if not customer:
                customer = get_customer(s, order.customer_id)
            if not item:
                items = get_order_items(s, order.order_id)
                item = items[0] if items else None
            if not product and item:
                product = get_product(s, item.product_id)

    rules = get_rule_set_for_order(order.order_date)
    is_change_of_mind = "mind" in reason.lower() or "unwanted" in reason.lower() or "dislike" in reason.lower()
    
    # 1. Suspended account check
    acc_status = (getattr(customer, "account_status", "active") or "active").lower() if customer else "active"
    if acc_status == "suspended":
        return RefundEligibilityResult(
            eligible=False,
            reason="Customer account is suspended. Escalation to Trust & Safety required.",
            policy_version=rules.version,
            reason_code="ACCOUNT_SUSPENDED",
            requires_human_approval=True,
            escalation_team="Trust & Safety",
            risk_flags=["account_suspended"],
        )

    # 2. Existing refund check
    order_refund_status = (getattr(order, "refund_status", "none") or "none").lower()
    item_return_status = (getattr(item, "return_status", "none") or "none") if item else "none"
    item_return_status = item_return_status.lower()
    if order_refund_status in ("approved", "completed", "requested") or item_return_status in ("approved", "completed", "requested"):
        return RefundEligibilityResult(
            eligible=False,
            reason=f"A refund has already been {order_refund_status} for this order/item.",
            policy_version=rules.version,
            reason_code="ALREADY_REFUNDED",
            requires_human_approval=False,
        )

    # 3. Delivery status check
    order_status = (getattr(order, "order_status", "") or "").lower()
    delivery_status = (getattr(order, "delivery_status", "") or "").lower()
    if delivery_status != "delivered" and order_status != "delivered":
        return RefundEligibilityResult(
            eligible=False,
            reason=f"Order is not delivered (status: '{delivery_status or order_status}'). Only delivered orders qualify for returns/refunds.",
            policy_version=rules.version,
            reason_code="NOT_DELIVERED",
            requires_human_approval=False,
        )

    # 4. Returnable check for change of mind
    if is_change_of_mind and product and not product.returnable:
        return RefundEligibilityResult(
            eligible=False,
            reason=f"Product '{product.product_name}' is marked non-returnable for change of mind.",
            policy_version=rules.version,
            reason_code="NON_RETURNABLE",
            requires_human_approval=False,
        )

    # 5. Window arithmetic
    deliv_date = parse_date(order.actual_delivery_date)
    if not deliv_date:
        deliv_date = parse_date(order.estimated_delivery_date) or parse_date(order.order_date)

    req_date = parse_date(previous_ticket_date_val) or parse_date(target_curr_date) or date.today()
    days_elapsed = (req_date - deliv_date).days if deliv_date else 0

    if is_change_of_mind:
        base_window = rules.change_of_mind_window_days
        loyalty_tier = getattr(customer, "loyalty_tier", "bronze").lower()
        extension = rules.loyalty_extensions.get(loyalty_tier, 0)
        total_window = base_window + extension
    else:
        total_window = rules.defect_window_days

    if days_elapsed > total_window:
        return RefundEligibilityResult(
            eligible=False,
            reason=f"Request is {days_elapsed} days after delivery, exceeding the {total_window}-day window under {rules.version}.",
            policy_version=rules.version,
            reason_code="WINDOW_EXPIRED",
            requires_human_approval=False,
        )

    # 6. Calculate Refund Amount
    final_price = Decimal(str(item.final_price)) if item else Decimal(str(order.subtotal))
    gst_amount = (final_price * rules.gst_rate).quantize(Decimal("0.01"))
    item_refund = final_price + gst_amount

    restocking_fee = Decimal("0.00")
    if rules.version == "v2" and is_change_of_mind and product:
        cat = product.category.lower() if product.category else ""
        if cat in RESTOCKING_CATEGORIES:
            calculated_fee = (item_refund * rules.restocking_fee_rate).quantize(Decimal("0.01"))
            restocking_fee = min(calculated_fee, rules.restocking_fee_cap)

    net_refund = max(Decimal("0.00"), item_refund - restocking_fee)
    
    # Cap against order total
    order_total = Decimal(str(order.total_amount))
    max_payable = min(net_refund, order_total)

    # 7. Approval threshold check
    needs_approval = order_total > rules.approval_threshold
    escalation_team = "Refunds & Payments" if needs_approval else None

    return RefundEligibilityResult(
        eligible=True,
        reason=f"Order is eligible for refund under {rules.version}. Eligible amount: INR {max_payable:.2f}.",
        policy_version=rules.version,
        reason_code="ELIGIBLE",
        max_refund_amount=max_payable,
        item_refund_amount=item_refund,
        restocking_fee=restocking_fee,
        requires_human_approval=needs_approval,
        escalation_team=escalation_team,
    )


def calculate_refund_amount(
    order,
    item=None,
    product=None,
    reason: str = "change_of_mind",
    **kwargs,
) -> dict:
    rules = get_rule_set_for_order(order.order_date)
    is_change_of_mind = "mind" in reason.lower() or "unwanted" in reason.lower() or "dislike" in reason.lower()
    
    final_price = Decimal(str(item.final_price)) if item else Decimal(str(order.subtotal))
    gst_amount = (final_price * rules.gst_rate).quantize(Decimal("0.01"))
    gross_refund = final_price + gst_amount

    restocking_fee = Decimal("0.00")
    if rules.version == "v2" and is_change_of_mind and product:
        cat = product.category.lower() if product.category else ""
        if cat in RESTOCKING_CATEGORIES:
            fee = (gross_refund * rules.restocking_fee_rate).quantize(Decimal("0.01"))
            restocking_fee = min(fee, rules.restocking_fee_cap)

    net_item_refund = max(Decimal("0.00"), gross_refund - restocking_fee)
    order_total = Decimal(str(order.total_amount))
    final_capped = min(net_item_refund, order_total)

    return {
        "policy_version": rules.version,
        "item_final_price": float(final_price),
        "gst_amount": float(gst_amount),
        "gross_item_refund": float(gross_refund),
        "restocking_fee": float(restocking_fee),
        "net_refund_amount": float(final_capped),
        "order_total": float(order_total),
        "is_capped": final_capped < net_item_refund,
    }


def check_return_eligibility(
    order,
    customer=None,
    item=None,
    product=None,
    reason: str = "defective",
    current_date_val: str | date | None = None,
    previous_ticket_date_val: str | date | None = None,
    current_date: str | date | None = None,
    **kwargs,
) -> ReturnEligibilityResult:
    target_curr_date = current_date or current_date_val

    if isinstance(order, str):
        from src.tools import _session
        from src.backend.repositories import get_order, get_order_items, get_product, get_customer
        with _session() as s:
            order_obj = get_order(s, order)
            if not order_obj:
                return ReturnEligibilityResult(
                    eligible=False,
                    reason=f"Order {order} not found.",
                    policy_version="v2",
                    reason_code="ORDER_NOT_FOUND",
                    window_days=0,
                    days_since_delivery=0,
                )
            order = order_obj
            if not customer:
                customer = get_customer(s, order.customer_id)
            if not item:
                items = get_order_items(s, order.order_id)
                item = items[0] if items else None
            if not product and item:
                product = get_product(s, item.product_id)

    refund_res = check_refund_eligibility(
        order=order,
        customer=customer,
        item=item,
        product=product,
        reason=reason,
        current_date_val=target_curr_date,
        previous_ticket_date_val=previous_ticket_date_val,
    )
    
    rules = get_rule_set_for_order(order.order_date)
    is_change_of_mind = "mind" in reason.lower() or "unwanted" in reason.lower()
    if is_change_of_mind:
        base_window = rules.change_of_mind_window_days
        loyalty_tier = getattr(customer, "loyalty_tier", "bronze").lower()
        window = base_window + rules.loyalty_extensions.get(loyalty_tier, 0)
    else:
        window = rules.defect_window_days

    deliv_date = parse_date(order.actual_delivery_date)
    req_date = parse_date(previous_ticket_date_val) or parse_date(target_curr_date) or date.today()
    days_elapsed = (req_date - deliv_date).days if deliv_date else 0

    remedy = "refund"
    if not is_change_of_mind and getattr(product, "replacement_available", False):
        remedy = "replacement_or_refund"

    return ReturnEligibilityResult(
        eligible=refund_res.eligible,
        reason=refund_res.reason,
        policy_version=refund_res.policy_version,
        reason_code=refund_res.reason_code,
        window_days=window,
        days_since_delivery=days_elapsed,
        requires_human_approval=refund_res.requires_human_approval,
        remedy=remedy,
        escalation_team=refund_res.escalation_team,
    )


def check_warranty_eligibility(
    product=None,
    order=None,
    issue_description: str = "",
    current_date_val: str | date | None = None,
    current_date: str | date | None = None,
    **kwargs,
) -> WarrantyEligibilityResult:
    target_curr_date = current_date or current_date_val or kwargs.get("date")

    # If first arg is order_id string and second is issue_description string
    if isinstance(product, str) and (isinstance(order, str) or not issue_description):
        order_id_str = product
        if isinstance(order, str) and not issue_description:
            issue_description = order
        from src.tools import _session
        from src.backend.repositories import get_order, get_order_items, get_product
        with _session() as s:
            order = get_order(s, order_id_str)
            items = get_order_items(s, order_id_str) if order else []
            product = get_product(s, items[0].product_id) if items else None

    # If order is passed as string
    if isinstance(order, str):
        from src.tools import _session
        from src.backend.repositories import get_order, get_order_items, get_product
        with _session() as s:
            order = get_order(s, order)
            if not product and order:
                items = get_order_items(s, order.order_id)
                product = get_product(s, items[0].product_id) if items else None

    desc_lower = (issue_description or "").lower()

    # Safety check
    if any(k in desc_lower for k in SAFETY_KEYWORDS):
        return WarrantyEligibilityResult(
            eligible=False,
            status="safety_hazard",
            reason="Device safety hazard detected (thermal/battery/smoke). Immediate shutdown advised and critical escalation.",
            warranty_months=getattr(product, "warranty_months", 12) if product else 12,
            expiry_date=None,
            remedy="safety_escalate",
            requires_human=True,
        )

    # Physical damage check
    if any(k in desc_lower for k in PHYSICAL_DAMAGE_KEYWORDS):
        return WarrantyEligibilityResult(
            eligible=False,
            status="not_covered",
            reason="Physical or liquid damage is not covered under manufacturer warranty. Paid repair is available.",
            warranty_months=getattr(product, "warranty_months", 12) if product else 12,
            expiry_date=None,
            remedy="paid_repair",
            requires_human=False,
        )

    deliv_date = parse_date(order.actual_delivery_date) if order else None
    if not deliv_date and order:
        deliv_date = parse_date(order.order_date)

    if not deliv_date:
        deliv_date = date.today()

    w_months = getattr(product, "warranty_months", 12) if product else 12
    expiry_date = deliv_date + relativedelta(months=w_months)

    curr_date = parse_date(target_curr_date) or date.today()
    days_left = (expiry_date - curr_date).days

    if days_left >= 0:
        return WarrantyEligibilityResult(
            eligible=True,
            status="active",
            reason=f"Product is covered under warranty until {expiry_date.isoformat()} ({days_left} days remaining).",
            warranty_months=w_months,
            expiry_date=expiry_date.isoformat(),
            days_remaining=days_left,
            remedy="warranty_service",
            requires_human=False,
        )
    else:
        return WarrantyEligibilityResult(
            eligible=False,
            status="expired",
            reason=f"Warranty expired on {expiry_date.isoformat()} ({abs(days_left)} days ago). Paid repair option available.",
            warranty_months=w_months,
            expiry_date=expiry_date.isoformat(),
            days_remaining=0,
            remedy="paid_repair",
            requires_human=False,
        )


def check_cancellation_eligibility(
    order,
    customer=None,
    **kwargs,
) -> CancellationEligibilityResult:
    if isinstance(order, str):
        from src.tools import _session
        from src.backend.repositories import get_order
        with _session() as s:
            order_obj = get_order(s, order)
            if not order_obj:
                return CancellationEligibilityResult(
                    eligible=False,
                    reason=f"Order {order} not found.",
                    order_status="unknown",
                    refund_applicable=False,
                )
            order = order_obj
    status = getattr(order, "order_status", "").lower()
    cancellation_status = getattr(order, "cancellation_status", "none").lower()

    if status in ("placed", "confirmed", "processing") and cancellation_status != "approved":
        is_prepaid = getattr(order, "payment_method", "").lower() != "cash_on_delivery"
        refund_amount = Decimal(str(order.total_amount)) if is_prepaid else Decimal("0.00")
        return CancellationEligibilityResult(
            eligible=True,
            reason=f"Order is in '{status}' stage and can be cancelled immediately.",
            order_status=status,
            refund_applicable=is_prepaid,
            refund_amount=refund_amount,
        )
    elif status in ("shipped", "out_for_delivery"):
        return CancellationEligibilityResult(
            eligible=False,
            reason=f"Order is already '{status}' and handed to courier. It cannot be cancelled in transit. Customer may refuse delivery at door.",
            order_status=status,
            refund_applicable=False,
        )
    elif status == "delivered":
        return CancellationEligibilityResult(
            eligible=False,
            reason="Order has already been delivered. Please use return or refund request.",
            order_status=status,
            refund_applicable=False,
        )
    elif status == "cancelled" or cancellation_status == "approved":
        return CancellationEligibilityResult(
            eligible=False,
            reason="Order is already cancelled.",
            order_status=status,
            refund_applicable=False,
        )
    else:
        return CancellationEligibilityResult(
            eligible=False,
            reason=f"Order status '{status}' is not eligible for direct cancellation.",
            order_status=status,
            refund_applicable=False,
        )
