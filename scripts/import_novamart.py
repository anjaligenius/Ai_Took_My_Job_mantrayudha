import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.db import (
    Base,
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
    init_db,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_novamart")

DATA_DIR = PROJECT_ROOT / "public"


def to_bool(val: str | None) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in ("true", "1", "yes", "y", "t")


def to_float(val: str | None, default: float = 0.0) -> float:
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def to_int(val: str | None, default: int = 0) -> int:
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(val))
    except ValueError:
        return default


def to_opt_str(val: str | None) -> str | None:
    if val is None or str(val).strip() == "":
        return None
    return str(val).strip()


def import_customers(session, file_path: Path):
    logger.info("Importing customers from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            customer = Customer(
                customer_id=r["customer_id"].strip(),
                first_name=r["first_name"].strip(),
                last_name=r["last_name"].strip(),
                email=r["email"].strip(),
                phone=r["phone"].strip(),
                gender=r["gender"].strip(),
                date_of_birth=r["date_of_birth"].strip(),
                city=r["city"].strip(),
                state=r["state"].strip(),
                pincode=r["pincode"].strip(),
                address=r["address"].strip(),
                customer_since=r["customer_since"].strip(),
                customer_segment=r["customer_segment"].strip(),
                account_status=r["account_status"].strip(),
                preferred_language=r["preferred_language"].strip(),
                total_orders=to_int(r.get("total_orders")),
                total_spend=to_float(r.get("total_spend")),
                loyalty_tier=r["loyalty_tier"].strip().lower(),
            )
            session.merge(customer)
            count += 1
    session.commit()
    logger.info("Imported %d customers", count)


def import_products(session, file_path: Path):
    logger.info("Importing products from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rating_val = to_opt_str(r.get("rating"))
            product = Product(
                product_id=r["product_id"].strip(),
                sku=r["sku"].strip(),
                product_name=r["product_name"].strip(),
                category=r["category"].strip(),
                subcategory=r["subcategory"].strip(),
                brand=r["brand"].strip(),
                description=r["description"].strip(),
                price=to_float(r.get("price")),
                mrp=to_float(r.get("mrp")),
                discount_percent=to_float(r.get("discount_percent")),
                stock_quantity=to_int(r.get("stock_quantity")),
                warranty_months=to_int(r.get("warranty_months"), 12),
                returnable=to_bool(r.get("returnable")),
                replacement_available=to_bool(r.get("replacement_available")),
                rating=float(rating_val) if rating_val is not None else None,
                review_count=to_int(r.get("review_count")),
                weight_kg=to_float(r.get("weight_kg")),
                color=r["color"].strip(),
                status=r["status"].strip(),
            )
            session.merge(product)
            count += 1
    session.commit()
    logger.info("Imported %d products", count)


def import_product_specs(session, products_dir: Path):
    if not products_dir.exists():
        logger.warning("Products spec directory %s does not exist", products_dir)
        return
    logger.info("Importing product specifications from %s", products_dir)
    count = 0
    for pfile in products_dir.glob("*.md"):
        content = pfile.read_text(encoding="utf-8")
        sections = re.split(r'\n(?=##\s)', content)
        for sec in sections:
            m = re.search(r'##\s*(.*?)\s*\((PROD-\d{5})\)', sec)
            if m:
                pid = m.group(2)
                prod = session.query(Product).filter_by(product_id=pid).first()
                if prod:
                    prod.spec_sheet_md = sec.strip()
                    count += 1
    session.commit()
    logger.info("Updated %d products with markdown specifications", count)


def import_orders(session, file_path: Path):
    logger.info("Importing orders from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            order = Order(
                order_id=r["order_id"].strip(),
                customer_id=r["customer_id"].strip(),
                order_date=r["order_date"].strip(),
                order_status=r["order_status"].strip(),
                payment_method=r["payment_method"].strip(),
                payment_status=r["payment_status"].strip(),
                subtotal=to_float(r.get("subtotal")),
                discount=to_float(r.get("discount")),
                shipping_fee=to_float(r.get("shipping_fee")),
                tax=to_float(r.get("tax")),
                total_amount=to_float(r.get("total_amount")),
                shipping_address=r["shipping_address"].strip(),
                city=r["city"].strip(),
                state=r["state"].strip(),
                estimated_delivery_date=to_opt_str(r.get("estimated_delivery_date")),
                actual_delivery_date=to_opt_str(r.get("actual_delivery_date")),
                tracking_number=to_opt_str(r.get("tracking_number")),
                courier=to_opt_str(r.get("courier")),
                delivery_status=r["delivery_status"].strip(),
                delivery_otp_verified=to_bool(r.get("delivery_otp_verified")),
                cancellation_status=r.get("cancellation_status", "none").strip(),
                refund_status=r.get("refund_status", "none").strip(),
            )
            session.merge(order)
            count += 1
    session.commit()
    logger.info("Imported %d orders", count)


def import_order_items(session, file_path: Path):
    logger.info("Importing order_items from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            item = OrderItem(
                order_item_id=r["order_item_id"].strip(),
                order_id=r["order_id"].strip(),
                product_id=r["product_id"].strip(),
                quantity=to_int(r.get("quantity"), 1),
                unit_price=to_float(r.get("unit_price")),
                discount=to_float(r.get("discount")),
                final_price=to_float(r.get("final_price")),
                item_status=r["item_status"].strip(),
                return_status=r.get("return_status", "none").strip(),
                refund_amount=to_float(r.get("refund_amount")),
            )
            session.merge(item)
            count += 1
    session.commit()
    logger.info("Imported %d order items", count)


def import_support_tickets(session, file_path: Path):
    logger.info("Importing support_tickets from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ticket = SupportTicket(
                ticket_id=r["ticket_id"].strip(),
                customer_id=r["customer_id"].strip(),
                order_id=to_opt_str(r.get("order_id")),
                created_at=r["created_at"].strip(),
                category=r["category"].strip(),
                subcategory=r["subcategory"].strip(),
                priority=r["priority"].strip(),
                status=r["status"].strip(),
                assigned_team=r["assigned_team"].strip(),
                issue_summary=r["issue_summary"].strip(),
                resolution=to_opt_str(r.get("resolution")),
                created_by=r["created_by"].strip(),
                resolved_at=to_opt_str(r.get("resolved_at")),
                conversation_id=to_opt_str(r.get("conversation_id")),
            )
            session.merge(ticket)
            count += 1
    session.commit()
    logger.info("Imported %d support tickets", count)


def import_reviews(session, file_path: Path):
    logger.info("Importing reviews from %s", file_path)
    count = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            review = Review(
                review_id=r["review_id"].strip(),
                product_id=r["product_id"].strip(),
                customer_id=r["customer_id"].strip(),
                order_id=to_opt_str(r.get("order_id")),
                rating=to_int(r.get("rating"), 5),
                title=r["title"].strip(),
                review_text=r["review_text"].strip(),
                review_date=r["review_date"].strip(),
                verified_purchase=to_bool(r.get("verified_purchase")),
                helpful_votes=to_int(r.get("helpful_votes")),
            )
            session.merge(review)
            count += 1
    session.commit()
    logger.info("Imported %d reviews", count)


def import_conversations(session, file_path: Path):
    logger.info("Importing conversations from %s", file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    count = 0
    for conv in data:
        conversation = Conversation(
            conversation_id=conv["conversation_id"].strip(),
            customer_id=conv["customer_id"].strip(),
            order_id=to_opt_str(conv.get("order_id")),
            ticket_id=to_opt_str(conv.get("ticket_id")),
            channel=conv.get("channel", "chat"),
            language=conv.get("language", "English"),
            started_at=conv.get("started_at", ""),
            status=conv.get("status", "closed"),
            handled_by=conv.get("handled_by", "bot"),
            messages_json=json.dumps(conv.get("messages", [])),
        )
        session.merge(conversation)
        count += 1
    session.commit()
    logger.info("Imported %d conversations", count)


def import_policies(session, policies_dir: Path):
    logger.info("Importing policies from %s", policies_dir)
    count = 0
    for pfile in policies_dir.glob("*.md"):
        content = pfile.read_text(encoding="utf-8")
        name = pfile.stem
        # Extract version and effective date if present
        version = "v1"
        if "_v2" in name:
            version = "v2"
        elif "_v1" in name:
            version = "v1"
        
        effective_date = "2026-01-01"
        if "2026-06-01" in content:
            effective_date = "2026-06-01"
        
        doc = PolicyDoc(
            policy_name=name,
            version=version,
            effective_date=effective_date,
            applies_to="All NovaMart orders/customers",
            content=content,
        )
        session.merge(doc)
        count += 1
    session.commit()
    logger.info("Imported %d policies", count)


def run_import(db_url: str | None = None, data_dir: Path | None = None):
    target_data_dir = data_dir or DATA_DIR
    if not target_data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {target_data_dir}")

    engine = get_engine(db_url)
    init_db(engine)
    SessionFactory = get_session_factory(engine)

    with SessionFactory() as session:
        import_customers(session, target_data_dir / "customers.csv")
        import_products(session, target_data_dir / "products.csv")
        import_product_specs(session, target_data_dir / "products")
        import_orders(session, target_data_dir / "orders.csv")
        import_order_items(session, target_data_dir / "order_items.csv")
        import_support_tickets(session, target_data_dir / "support_tickets.csv")
        import_reviews(session, target_data_dir / "reviews.csv")
        import_conversations(session, target_data_dir / "conversations.json")
        import_policies(session, target_data_dir / "policies")

    logger.info("All NovaMart data imported successfully!")


if __name__ == "__main__":
    run_import()
