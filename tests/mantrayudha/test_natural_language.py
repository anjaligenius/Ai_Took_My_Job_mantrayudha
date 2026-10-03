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


def test_greeting_english():
    """Verify that a standard English greeting is answered politely without escalation."""
    res = run_orchestrator(
        user_message="Hello, can you help me today?",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ANSWER"
    assert "novamart" in res["reply"].lower()
    assert res["risk_level"] == "LOW"


def test_greeting_hinglish():
    """Verify that a Hinglish greeting is answered courteously."""
    res = run_orchestrator(
        user_message="Namaste, kaise ho?",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ANSWER"
    assert "novamart" in res["reply"].lower()


def test_hinglish_tracking_inquiry():
    """Verify that a tracking inquiry phrased in Hinglish is parsed as tracking intent."""
    res = run_orchestrator(
        user_message="Mera order kahan hai ORD-000001, status batao?",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ANSWER"
    assert "ORD-000001" in res["reply"] or "delivered" in res["reply"].lower()


def test_catalog_product_inquiry():
    """Verify that customer asking about products receives product catalog details."""
    res = run_orchestrator(
        user_message="What laptops do you sell?",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ANSWER"
    assert "catalog" in res["reply"].lower() or "novabook" in res["reply"].lower()


def test_pure_gibberish_escalated():
    """Verify that pure unpronounceable gibberish is safely escalated to human specialists."""
    res = run_orchestrator(
        user_message="asdkjhasd nonsense qwerty",
        customer_id="CUST-00001",
        current_date="2026-05-01",
    )
    assert res["decision"] == "ESCALATE"
    assert "unrecognized" in res.get("risk_signals", []) or "unrecognized_intent" in res.get("risk_signals", [])
