import pytest
from src.backend.db import get_engine, get_session_factory, Order, Customer, OrderItem, Product
from src.backend.seed import seed
from src import tools
from src.policy.engine import check_return_eligibility


@pytest.fixture(autouse=True)
def seeded_db():
    engine = get_engine("sqlite:///:memory:")
    tools.configure_db(engine)
    session = get_session_factory(engine)()
    seed(session)
    yield


def test_non_returnable_item_blocked_for_change_of_mind():
    # In-ear earbuds or chargers with returnable = False
    prod = Product(product_id="P-NR", product_name="Charger", returnable=False, replacement_available=True)
    order = Order(order_id="O-NR", order_date="2026-04-01", order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-04-05", total_amount=1000.0)
    cust = Customer(customer_id="C1", loyalty_tier="bronze", account_status="active")
    item = OrderItem(order_item_id="I1", final_price=1000.0)

    res = check_return_eligibility(order, cust, item, prod, reason="change of mind", current_date_val="2026-04-08")
    assert res.eligible is False
    assert res.reason_code == "NON_RETURNABLE"


def test_non_returnable_item_allowed_for_defects():
    # If item is dead on arrival or defective, it CAN be returned even if returnable = False
    prod = Product(product_id="P-NR", product_name="Charger", returnable=False, replacement_available=True)
    order = Order(order_id="O-NR", order_date="2026-04-01", order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-04-05", total_amount=1000.0)
    cust = Customer(customer_id="C1", loyalty_tier="bronze", account_status="active")
    item = OrderItem(order_item_id="I1", final_price=1000.0)

    res = check_return_eligibility(order, cust, item, prod, reason="defective dead on arrival", current_date_val="2026-04-08")
    assert res.eligible is True


def test_loyalty_tier_extension():
    # Under v1, base change of mind window = 10 days.
    # Gold gets +2 days (12 days total), Platinum gets +3 days (13 days total).
    order = Order(order_id="O-LOY", order_date="2026-04-01", order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-04-01", total_amount=2000.0)
    prod = Product(product_id="P1", product_name="Shoes", returnable=True)
    item = OrderItem(order_item_id="I1", final_price=2000.0)

    # Day 11 (2026-04-12): Bronze is expired (10 days)
    cust_bronze = Customer(customer_id="CB", loyalty_tier="bronze", account_status="active")
    res_b = check_return_eligibility(order, cust_bronze, item, prod, reason="change_of_mind", current_date_val="2026-04-12")
    assert res_b.eligible is False

    # Day 11: Gold is eligible (10 + 2 = 12 days)
    cust_gold = Customer(customer_id="CG", loyalty_tier="gold", account_status="active")
    res_g = check_return_eligibility(order, cust_gold, item, prod, reason="change_of_mind", current_date_val="2026-04-12")
    assert res_g.eligible is True
    assert res_g.window_days == 12
