import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.db import (
    Conversation,
    Customer,
    Order,
    OrderItem,
    PolicyDoc,
    Product,
    Review,
    SupportTicket,
    get_engine,
    get_session_factory,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("validate_dataset")

EXPECTED_COUNTS = {
    Customer: 1500,
    Product: 300,
    Order: 8000,
    OrderItem: 12444,
    SupportTicket: 2500,
    Review: 3000,
    Conversation: 1500,
    PolicyDoc: 10,
}


def validate_counts(session) -> bool:
    all_ok = True
    for model, expected in EXPECTED_COUNTS.items():
        actual = session.query(model).count()
        if model == SupportTicket and actual >= expected:
            logger.info("Count match for %s: %d (>= baseline %d)", model.__name__, actual, expected)
            continue
        if actual != expected:
            logger.error(
                "Count mismatch for %s: expected %d, got %d",
                model.__name__,
                expected,
                actual,
            )
            all_ok = False
        else:
            logger.info("Count match for %s: %d", model.__name__, actual)
    return all_ok


def validate_foreign_keys(session) -> bool:
    all_ok = True
    # 1. Orders -> Customers
    invalid_orders = (
        session.query(Order.order_id, Order.customer_id)
        .outerjoin(Customer, Order.customer_id == Customer.customer_id)
        .filter(Customer.customer_id == None)  # noqa: E711
        .all()
    )
    if invalid_orders:
        logger.error("Found %d orders with invalid customer_id", len(invalid_orders))
        all_ok = False
    else:
        logger.info("All orders link to valid customers")

    # 2. OrderItems -> Orders
    invalid_order_items_order = (
        session.query(OrderItem.order_item_id)
        .outerjoin(Order, OrderItem.order_id == Order.order_id)
        .filter(Order.order_id == None)  # noqa: E711
        .all()
    )
    if invalid_order_items_order:
        logger.error("Found %d order items with invalid order_id", len(invalid_order_items_order))
        all_ok = False
    else:
        logger.info("All order items link to valid orders")

    # 3. OrderItems -> Products
    invalid_order_items_product = (
        session.query(OrderItem.order_item_id)
        .outerjoin(Product, OrderItem.product_id == Product.product_id)
        .filter(Product.product_id == None)  # noqa: E711
        .all()
    )
    if invalid_order_items_product:
        logger.error("Found %d order items with invalid product_id", len(invalid_order_items_product))
        all_ok = False
    else:
        logger.info("All order items link to valid products")

    # 4. SupportTickets -> Customers
    invalid_tickets_customer = (
        session.query(SupportTicket.ticket_id)
        .outerjoin(Customer, SupportTicket.customer_id == Customer.customer_id)
        .filter(Customer.customer_id == None)  # noqa: E711
        .all()
    )
    if invalid_tickets_customer:
        logger.error("Found %d tickets with invalid customer_id", len(invalid_tickets_customer))
        all_ok = False
    else:
        logger.info("All support tickets link to valid customers")

    # 5. Reviews -> Products
    invalid_reviews_product = (
        session.query(Review.review_id)
        .outerjoin(Product, Review.product_id == Product.product_id)
        .filter(Product.product_id == None)  # noqa: E711
        .all()
    )
    if invalid_reviews_product:
        logger.error("Found %d reviews with invalid product_id", len(invalid_reviews_product))
        all_ok = False
    else:
        logger.info("All reviews link to valid products")

    return all_ok


def validate_policies(session) -> bool:
    all_ok = True
    v1_refund = session.query(PolicyDoc).filter_by(policy_name="refund_policy_v1").first()
    v2_refund = session.query(PolicyDoc).filter_by(policy_name="refund_policy_v2").first()
    if not v1_refund or not v2_refund:
        logger.error("Missing versioned refund policies in database")
        all_ok = False
    else:
        logger.info("Versioned refund policies found: %s, %s", v1_refund.version, v2_refund.version)
    return all_ok


def main():
    engine = get_engine()
    SessionFactory = get_session_factory(engine)

    with SessionFactory() as session:
        counts_ok = validate_counts(session)
        fk_ok = validate_foreign_keys(session)
        policies_ok = validate_policies(session)

    if counts_ok and fk_ok and policies_ok:
        logger.info("SUCCESS: All NovaMart database validations PASSED!")
        sys.exit(0)
    else:
        logger.error("FAILURE: Database validation checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
