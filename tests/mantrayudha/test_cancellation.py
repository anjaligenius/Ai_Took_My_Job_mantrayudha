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


def test_cancel_placed_order_succeeds_with_refund():
    # ORD-000003 is placed (unshipped, prepaid via UPI)
    res = tools.cancel_order("ORD-000003", customer_id="CUST-00002")
    assert res["success"] is True
    assert res["order_status"] == "cancelled"
    assert res["refund_issued"] is True
    assert res["refund_amount"] > 0
    assert res["verified"] is True


def test_cancel_shipped_order_refused():
    # ORD-000002 is shipped / in transit
    res = tools.cancel_order("ORD-000002", customer_id="CUST-00001")
    assert res["success"] is False
    assert "cannot be cancelled in transit" in res["reason"]


def test_cancel_delivered_order_refused():
    # ORD-000001 is delivered
    res = tools.cancel_order("ORD-000001", customer_id="CUST-00001")
    assert res["success"] is False
    assert "already been delivered" in res["reason"]
