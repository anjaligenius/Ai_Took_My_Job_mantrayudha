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


def test_legal_threat_escalation():
    res = run_orchestrator("If I don't get my money back today I am filing an FIR and taking NovaMart to consumer court", customer_id="CUST-00001")
    assert res["decision"] == "ESCALATE"
    assert "Customer Experience" in res["reply"] or "ticket #" in res["reply"]


def test_safety_hazard_critical_escalation():
    res = run_orchestrator("My charger is overheating and battery is swelling with smoke coming out!", customer_id="CUST-00001")
    assert res["decision"] == "ESCALATE"
    assert "Technical Support" in res["reply"] or "ticket #" in res["reply"]


def test_suspended_account_escalation():
    # CUST-00003 is suspended
    res = run_orchestrator("Where is my order?", customer_id="CUST-00003")
    assert res["decision"] == "ESCALATE"
    assert "Trust & Safety" in res["reply"] or "ticket #" in res["reply"]
