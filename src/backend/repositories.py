import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.db import (
    Conversation,
    Customer,
    Order,
    OrderItem,
    PolicyDoc,
    Product,
    RefundRecord,
    ReturnRecord,
    Review,
    SupportTicket,
)

logger = logging.getLogger("support_agent.repositories")


def normalize_order_id(order_id: str | int) -> str:
    s = str(order_id).strip()
    if s.isdigit():
        return f"ORD-{int(s):06d}"
    return s.upper()


def normalize_customer_id(cust_id: str | int) -> str:
    s = str(cust_id).strip()
    if s.isdigit():
        return f"CUST-{int(s):05d}"
    return s.upper()


def get_customer(session: Session, identifier: str) -> Optional[Customer]:
    """Lookup customer by customer_id (e.g. CUST-00001 or 1) or email."""
    if not identifier:
        return None
    ident = str(identifier).strip()
    if "@" in ident:
        return session.query(Customer).filter_by(email=ident).first()
    norm_id = normalize_customer_id(ident)
    cust = session.query(Customer).filter_by(customer_id=norm_id).first()
    if not cust:
        cust = session.query(Customer).filter_by(customer_id=ident).first()
    return cust


def get_order(session: Session, order_id: str | int) -> Optional[Order]:
    """Lookup order by order_id (e.g. ORD-000001, 1001, etc.)."""
    if not order_id:
        return None
    norm_id = normalize_order_id(order_id)
    order = session.query(Order).filter_by(order_id=norm_id).first()
    if not order:
        order = session.query(Order).filter_by(order_id=str(order_id).strip()).first()
    return order


def get_orders_by_customer(session: Session, customer_id: str) -> List[Order]:
    norm_id = normalize_customer_id(customer_id)
    return session.query(Order).filter_by(customer_id=norm_id).order_by(Order.order_date.desc()).all()


def get_order_items(session: Session, order_id: str | int) -> List[OrderItem]:
    norm_id = normalize_order_id(order_id)
    return session.query(OrderItem).filter_by(order_id=norm_id).all()


def get_product(session: Session, product_id_or_sku: str) -> Optional[Product]:
    if not product_id_or_sku:
        return None
    ident = str(product_id_or_sku).strip()
    prod = session.query(Product).filter_by(product_id=ident).first()
    if not prod:
        prod = session.query(Product).filter_by(sku=ident).first()
    if not prod:
        # Partial name match
        prod = session.query(Product).filter(Product.product_name.ilike(f"%{ident}%")).first()
    return prod


def get_product_specs(session: Session, product_id_or_sku: str) -> Optional[str]:
    """Retrieve authoritative markdown specification for a product."""
    prod = get_product(session, product_id_or_sku)
    if not prod:
        return None
    if prod.spec_sheet_md:
        return prod.spec_sheet_md

    # Fallback to public/products markdown files on disk
    from pathlib import Path
    import re
    prod_dir = Path("public/products")
    if prod_dir.exists():
        for pfile in prod_dir.glob("*.md"):
            content = pfile.read_text(encoding="utf-8")
            pattern = rf'##\s*.*?\s*\({re.escape(prod.product_id)}\)(.*?)(?=\n##\s|\Z)'
            m = re.search(pattern, content, re.DOTALL)
            if m:
                spec = m.group(0).strip()
                prod.spec_sheet_md = spec
                try:
                    session.commit()
                except Exception:
                    pass
                return spec
    return None


def get_customer_tickets(session: Session, customer_id: str) -> List[SupportTicket]:
    norm_id = normalize_customer_id(customer_id)
    return session.query(SupportTicket).filter_by(customer_id=norm_id).order_by(SupportTicket.created_at.desc()).all()


def get_customer_conversations(session: Session, customer_id: str) -> List[Conversation]:
    norm_id = normalize_customer_id(customer_id)
    return session.query(Conversation).filter_by(customer_id=norm_id).order_by(Conversation.started_at.desc()).all()


def verify_order_ownership(session: Session, customer_id: str, order_id: str | int) -> bool:
    order = get_order(session, order_id)
    if not order:
        return False
    norm_cust_id = normalize_customer_id(customer_id)
    return order.customer_id == norm_cust_id


def create_support_ticket(
    session: Session,
    customer_id: str,
    category: str,
    subcategory: str,
    issue_summary: str,
    order_id: Optional[str] = None,
    priority: str = "medium",
    assigned_team: str = "Tier 1 Support",
    created_by: str = "agent",
) -> SupportTicket:
    norm_cust = normalize_customer_id(customer_id)
    norm_order = normalize_order_id(order_id) if order_id else None

    # Generate ticket ID
    next_num = session.query(SupportTicket).count() + 1
    ticket_id = f"TICK-{next_num:05d}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ticket = SupportTicket(
        ticket_id=ticket_id,
        customer_id=norm_cust,
        order_id=norm_order,
        created_at=now_str,
        category=category,
        subcategory=subcategory,
        priority=priority,
        status="open",
        assigned_team=assigned_team,
        issue_summary=issue_summary,
        resolution=None,
        created_by=created_by,
        resolved_at=None,
        conversation_id=None,
    )
    session.add(ticket)
    session.commit()
    logger.info("Created support ticket %s for customer %s (team: %s)", ticket_id, norm_cust, assigned_team)
    return ticket


def execute_cancel_order(
    session: Session,
    order_id: str | int,
    reason: str = "Customer requested cancellation",
) -> dict:
    order = get_order(session, order_id)
    if not order:
        return {"success": False, "error": f"Order {order_id} not found"}

    order.order_status = "cancelled"
    order.cancellation_status = "approved"
    
    is_prepaid = order.payment_method.lower() != "cash_on_delivery"
    if is_prepaid:
        order.refund_status = "completed"
        order.payment_status = "refunded"

    session.commit()
    return {
        "success": True,
        "order_id": order.order_id,
        "order_status": "cancelled",
        "cancellation_status": "approved",
        "refund_issued": is_prepaid,
        "refund_amount": order.total_amount if is_prepaid else 0.0,
    }


def execute_create_refund(
    session: Session,
    order_id: str | int,
    amount: float,
    reason: str,
    policy_version: str,
    order_item_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    order = get_order(session, order_id)
    if not order:
        return {"success": False, "error": f"Order {order_id} not found"}

    idem_key = idempotency_key or f"REF-{order.order_id}-{order_item_id or 'ALL'}-{now_key()}"
    existing = session.query(RefundRecord).filter_by(idempotency_key=idem_key).first()
    if existing:
        return {
            "success": True,
            "refund_id": existing.refund_id,
            "order_id": order.order_id,
            "amount": existing.amount,
            "status": existing.status,
            "idempotent": True,
        }

    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rec = RefundRecord(
        refund_id=refund_id,
        order_id=order.order_id,
        order_item_id=order_item_id,
        customer_id=order.customer_id,
        amount=amount,
        reason=reason,
        status="requested",
        policy_version=policy_version,
        created_at=now_str,
        idempotency_key=idem_key,
    )
    session.add(rec)
    order.refund_status = "requested"
    session.commit()
    return {
        "success": True,
        "refund_id": refund_id,
        "order_id": order.order_id,
        "amount": amount,
        "status": "requested",
    }


def execute_create_return(
    session: Session,
    order_id: str | int,
    reason: str,
    order_item_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    order = get_order(session, order_id)
    if not order:
        return {"success": False, "error": f"Order {order_id} not found"}

    idem_key = idempotency_key or f"RET-{order.order_id}-{order_item_id or 'ALL'}-{now_key()}"
    existing = session.query(ReturnRecord).filter_by(idempotency_key=idem_key).first()
    if existing:
        return {
            "success": True,
            "return_id": existing.return_id,
            "order_id": order.order_id,
            "status": existing.status,
            "idempotent": True,
        }

    return_id = f"RET-{uuid.uuid4().hex[:8].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rec = ReturnRecord(
        return_id=return_id,
        order_id=order.order_id,
        order_item_id=order_item_id,
        customer_id=order.customer_id,
        reason=reason,
        status="requested",
        created_at=now_str,
        idempotency_key=idem_key,
    )
    session.add(rec)
    if order_item_id:
        item = session.query(OrderItem).filter_by(order_item_id=order_item_id).first()
        if item:
            item.return_status = "requested"
    session.commit()
    return {
        "success": True,
        "return_id": return_id,
        "order_id": order.order_id,
        "status": "requested",
    }


def now_key() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")


def get_product_reviews(session: Session, product_id_or_sku: str, limit: int = 5) -> List[Review]:
    """Retrieve verified customer reviews for a product."""
    prod = get_product(session, product_id_or_sku)
    if not prod:
        return []
    return (
        session.query(Review)
        .filter_by(product_id=prod.product_id)
        .order_by(Review.review_date.desc())
        .limit(limit)
        .all()
    )
