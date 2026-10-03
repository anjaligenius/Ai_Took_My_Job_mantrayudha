import pytest
from decimal import Decimal
from src.backend.db import get_engine, get_session_factory, Order, Customer, OrderItem, Product
from src.backend.seed import seed
from src.policy.engine import (
    get_applicable_policy,
    check_refund_eligibility,
    calculate_refund_amount,
)
from src import tools


@pytest.fixture(autouse=True)
def seeded_db():
    engine = get_engine("sqlite:///:memory:")
    tools.configure_db(engine)
    session = get_session_factory(engine)()
    seed(session)
    yield


def test_policy_version_by_order_placement_date():
    # Order placed before 2026-06-01 -> v1
    v1_policy = get_applicable_policy("refund", "2026-04-10 10:00:00")
    assert v1_policy["version"] == "v1"
    assert v1_policy["rules"]["approval_threshold"] == 100000.0
    assert v1_policy["rules"]["change_of_mind_window_days"] == 10
    assert v1_policy["rules"]["restocking_fee_rate"] == 0.0

    # Order placed on or after 2026-06-01 -> v2
    v2_policy = get_applicable_policy("refund", "2026-06-01 00:00:00")
    assert v2_policy["version"] == "v2"
    assert v2_policy["rules"]["approval_threshold"] == 75000.0
    assert v2_policy["rules"]["change_of_mind_window_days"] == 7
    assert v2_policy["rules"]["restocking_fee_rate"] == 0.05
    assert "laptops" in v2_policy["rules"]["restocking_categories"]


def test_v2_restocking_fee_calculation():
    # Laptop under v2 (ORD-000004 placed on 2026-06-10, item price 85000)
    # GST = 85000 * 0.18 = 15300; Gross = 100300
    # 5% of 100300 = 5015; Capped at 2500 max fee!
    # Net refund = 100300 - 2500 = 97800
    calc = calculate_refund_amount(
        order=Order(order_id="TEST-V2", order_date="2026-06-10", total_amount=100300.0),
        item=OrderItem(order_item_id="OI-TEST", final_price=85000.0),
        product=Product(product_id="P-LAP", category="Laptops", product_name="NovaBook"),
        reason="change_of_mind",
    )
    assert calc["policy_version"] == "v2"
    assert calc["restocking_fee"] == 2500.0
    assert calc["net_refund_amount"] == 97800.0


def test_v2_no_restocking_fee_on_defective():
    # Defective return on Laptop under v2: NO restocking fee
    calc = calculate_refund_amount(
        order=Order(order_id="TEST-V2", order_date="2026-06-10", total_amount=100300.0),
        item=OrderItem(order_item_id="OI-TEST", final_price=85000.0),
        product=Product(product_id="P-LAP", category="Laptops", product_name="NovaBook"),
        reason="defective item dead on arrival",
    )
    assert calc["restocking_fee"] == 0.0
    assert calc["net_refund_amount"] == 100300.0


def test_v1_approval_threshold_escalation():
    # v1 threshold is 100,000 INR
    res_below = check_refund_eligibility(
        order=Order(order_id="O1", order_date="2026-04-01", total_amount=95000.0, order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-04-05"),
        customer=Customer(customer_id="C1", account_status="active", loyalty_tier="bronze"),
        item=OrderItem(final_price=1000.0),
        product=Product(returnable=True),
        reason="change_of_mind",
        current_date_val="2026-04-08",
    )
    assert res_below.requires_human_approval is False

    res_above = check_refund_eligibility(
        order=Order(order_id="O2", order_date="2026-04-01", total_amount=105000.0, order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-04-05"),
        customer=Customer(customer_id="C1", account_status="active", loyalty_tier="bronze"),
        item=OrderItem(final_price=1000.0),
        product=Product(returnable=True),
        reason="change_of_mind",
        current_date_val="2026-04-08",
    )
    assert res_above.requires_human_approval is True
    assert res_above.escalation_team == "Refunds & Payments"


def test_v2_approval_threshold_lowered_to_75000():
    # Under v2 (order date >= 2026-06-01), threshold is lowered to 75,000 INR
    # An order of 85,000 needs human approval under v2
    res_v2 = check_refund_eligibility(
        order=Order(order_id="O3", order_date="2026-06-05", total_amount=85000.0, order_status="delivered", delivery_status="delivered", actual_delivery_date="2026-06-10"),
        customer=Customer(customer_id="C1", account_status="active", loyalty_tier="bronze"),
        item=OrderItem(final_price=1000.0),
        product=Product(returnable=True),
        reason="change_of_mind",
        current_date_val="2026-06-12",
    )
    assert res_v2.policy_version == "v2"
    assert res_v2.requires_human_approval is True
