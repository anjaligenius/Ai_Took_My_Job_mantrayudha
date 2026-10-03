import pytest
from src.backend.db import get_engine, get_session_factory
from src.backend.seed import seed
from src import tools


@pytest.fixture(autouse=True)
def seeded_db():
    engine = get_engine("sqlite:///:memory:")
    tools.configure_db(engine)
    session = get_session_factory(engine)()
    seed(session)
    yield


def test_refund_exact_gst_calculation():
    # Final price 2499.0 + 18% GST (449.82) = 2948.82
    calc = tools.calculate_refund("ORD-000001", reason="change_of_mind")
    assert calc["item_final_price"] == 2499.0
    assert calc["gst_amount"] == 449.82
    assert calc["net_refund_amount"] == 2948.82


def test_refund_capped_at_order_total():
    # If customer demands ₹50,000 for order ORD-000001, refund is capped at authorized total
    elig = tools.check_refund_eligibility("ORD-000001", reason="damaged", current_date="2026-04-18")
    assert elig["eligible"] is True
    assert elig["max_refund_amount"] <= 2948.82


def test_refund_refused_for_undelivered_order():
    # ORD-000002 is shipped, not delivered
    res = tools.check_refund_eligibility("ORD-000002")
    assert res["eligible"] is False
    assert "only delivered orders" in res["reason"].lower()


def test_refund_idempotency():
    # Executing the same refund twice does not create duplicate entries
    r1 = tools.create_refund(
        order_id="ORD-000001",
        amount=2948.82,
        reason="Defective item",
        idempotency_key="IDEM-TEST-101",
        current_date="2026-04-18",
    )
    assert r1["success"] is True

    r2 = tools.create_refund(
        order_id="ORD-000001",
        amount=2948.82,
        reason="Defective item",
        idempotency_key="IDEM-TEST-101",
        current_date="2026-04-18",
    )
    assert r2["success"] is True
    assert r2.get("idempotent") is True
    assert r1["refund_id"] == r2["refund_id"]
