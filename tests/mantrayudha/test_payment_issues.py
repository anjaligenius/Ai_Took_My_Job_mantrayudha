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


def test_payment_status_paid_order():
    """Verify that an order with status 'paid' is retrieved accurately without hallucination."""
    res = tools.check_payment_status("ORD-000001")
    assert res["status"] == "paid"
    assert res["method"] in ["credit_card", "upi", "debit_card", "net_banking"]
    assert res["amount"] > 0


def test_payment_inquiry_orchestrator():
    """Verify that a customer inquiry about payment status returns ANSWER with factual details."""
    res = run_orchestrator(
        user_message="Did my payment go through for order ORD-000001?",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ANSWER"
    assert "paid" in res["reply"].lower() or "credit_card" in res["reply"].lower()
    assert res["risk_level"] == "LOW"


def test_payment_inquiry_cross_account_blocked():
    """Verify that inquiring about someone else's order triggers security escalation."""
    res = run_orchestrator(
        user_message="Did my payment go through for order ORD-000001?",
        customer_id="CUST-00615",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ESCALATE"
    assert res["risk_level"] == "HIGH"


def test_process_payment_idempotency_check():
    """Verify that paying an already paid order is refused safely."""
    res = tools.process_payment("ORD-000001", method="upi")
    assert res["success"] is False
    assert "already paid" in res["reason"].lower()
