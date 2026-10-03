import pytest
from src.backend.db import get_engine, get_session_factory
from src.backend.seed import seed
from src import tools
from src.orchestrator import run_orchestrator


@pytest.fixture(autouse=True)
def seeded_db():
    engine = get_engine("sqlite:///:memory:")
    tools.configure_db(engine)
    session = get_session_factory(engine)()
    seed(session)
    yield


def test_customer_cannot_cancel_other_customer_order():
    # ORD-000003 belongs to CUST-00002. CUST-00001 attempts to cancel it.
    res = tools.cancel_order("ORD-000003", customer_id="CUST-00001")
    assert res["success"] is False
    assert "Authorization failed" in res["error"]


def test_customer_cannot_refund_other_customer_order():
    # ORD-000003 belongs to CUST-00002. CUST-00001 attempts to refund it.
    res = tools.create_refund("ORD-000003", amount=500.0, reason="test", customer_id="CUST-00001")
    assert res["success"] is False
    assert "Authorization failed" in res["error"]


def test_orchestrator_escalates_on_cross_account_access():
    res = run_orchestrator("Where is order ORD-000003?", customer_id="CUST-00001")
    assert res["decision"] == "ESCALATE"
    assert "Trust & Safety" in res["reply"]
