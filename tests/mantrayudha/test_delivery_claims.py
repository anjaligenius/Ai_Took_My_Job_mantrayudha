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


def test_otp_verified_non_delivery_claim_escalates():
    # Customer claims package never delivered, but ORD-000001 was delivered and OTP verified
    claim = tools.check_delivery_claim("ORD-000001", "I never received this parcel")
    assert claim["contradiction"] is True
    assert claim["action"] == "ESCALATE"
    assert claim["escalation_team"] == "Logistics Desk"


def test_orchestrator_escalates_on_otp_contradiction():
    # Calling the orchestrator with customer CUST-00001 for their own delivered order ORD-000001
    res = run_orchestrator("I never received order ORD-000001. Give me refund now.", customer_id="CUST-00001")
    assert res["decision"] == "ESCALATE"
    assert "Logistics Desk" in str(res.get("reply")) or res.get("agent") == "escalate"
