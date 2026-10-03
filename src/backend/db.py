import os
from pathlib import Path
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "support_agent.db"


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(50))
    gender: Mapped[str] = mapped_column(String(20))
    date_of_birth: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(Text)
    customer_since: Mapped[str] = mapped_column(String(20))
    customer_segment: Mapped[str] = mapped_column(String(50))
    account_status: Mapped[str] = mapped_column(String(50))  # active, suspended
    preferred_language: Mapped[str] = mapped_column(String(50))
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_spend: Mapped[float] = mapped_column(Float, default=0.0)
    loyalty_tier: Mapped[str] = mapped_column(String(50))  # bronze, silver, gold, platinum

    orders = relationship("Order", back_populates="customer")
    tickets = relationship("SupportTicket", back_populates="customer")
    reviews = relationship("Review", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), index=True)
    subcategory: Mapped[str] = mapped_column(String(100))
    brand: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    mrp: Mapped[float] = mapped_column(Float)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    warranty_months: Mapped[int] = mapped_column(Integer, default=12)
    returnable: Mapped[bool] = mapped_column(Boolean, default=True)
    replacement_available: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    color: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    spec_sheet_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), index=True)
    order_date: Mapped[str] = mapped_column(String(30), index=True)
    order_status: Mapped[str] = mapped_column(String(50))  # placed, confirmed, processing, shipped, out_for_delivery, delivered, cancelled, returned
    payment_method: Mapped[str] = mapped_column(String(50))
    payment_status: Mapped[str] = mapped_column(String(50))  # paid, pending, failed, refunded, partially_refunded
    subtotal: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float)
    shipping_fee: Mapped[float] = mapped_column(Float)
    tax: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    shipping_address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    estimated_delivery_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actual_delivery_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    courier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(50))  # delivered, out_for_delivery, in_transit, pending, failed
    delivery_otp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    cancellation_status: Mapped[str] = mapped_column(String(50), default="none")  # none, requested, approved, rejected, auto_cancelled
    refund_status: Mapped[str] = mapped_column(String(50), default="none")  # none, requested, approved, rejected, completed

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    tickets = relationship("SupportTicket", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), index=True)
    product_id: Mapped[str] = mapped_column(String(32), ForeignKey("products.product_id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    final_price: Mapped[float] = mapped_column(Float)
    item_status: Mapped[str] = mapped_column(String(50))
    return_status: Mapped[str] = mapped_column(String(50), default="none")  # none, requested, approved, completed, rejected
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    ticket_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("orders.order_id"), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str] = mapped_column(String(100))
    subcategory: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(50))  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(50))  # open, in_progress, resolved, closed
    assigned_team: Mapped[str] = mapped_column(String(100))
    issue_summary: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(50))
    resolved_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    customer = relationship("Customer", back_populates="tickets")
    order = relationship("Order", back_populates="tickets")


class Review(Base):
    __tablename__ = "reviews"

    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(32), ForeignKey("products.product_id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    review_text: Mapped[str] = mapped_column(Text)
    review_date: Mapped[str] = mapped_column(String(20))
    verified_purchase: Mapped[bool] = mapped_column(Boolean, default=True)
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0)

    product = relationship("Product", back_populates="reviews")
    customer = relationship("Customer", back_populates="reviews")


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.customer_id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(50))
    handled_by: Mapped[str] = mapped_column(String(50))
    messages_json: Mapped[str] = mapped_column(Text)


class PolicyDoc(Base):
    __tablename__ = "policy_docs"

    policy_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    effective_date: Mapped[str] = mapped_column(String(20))
    applies_to: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)


class RefundRecord(Base):
    """Immutable audit record for refunds."""
    __tablename__ = "refund_records"

    refund_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), index=True)
    order_item_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="requested")  # requested, approved, completed, escalated
    policy_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)


class ReturnRecord(Base):
    """Immutable audit record for return requests."""
    __tablename__ = "return_records"

    return_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), index=True)
    order_item_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="requested")  # requested, approved, rejected
    created_at: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)


def get_engine(db_url: str | None = None):
    default_url = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    url = db_url or os.environ.get("SUPPORT_AGENT_DB_URL", default_url)
    return create_engine(url, echo=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def get_session_factory(engine):
    return sessionmaker(bind=engine)
