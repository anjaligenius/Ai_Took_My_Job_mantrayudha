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


def test_ambiguity_when_multiple_orders_match():
    # CUST-00001 has multiple orders (ORD-000001, ORD-000002)
    res = run_orchestrator("I want to return the item I received", customer_id="CUST-00001")
    assert res["decision"] == "ASK"
    assert "which one" in res["reply"].lower() or "matching orders" in res["reply"].lower()


def test_ambiguity_non_existent_order():
    # Customer provides order ID that does not exist in DB
    res = run_orchestrator("Where is order ORD-999999?", customer_id="CUST-00001")
    assert res["decision"] == "ASK"
    assert "couldn't find" in res["reply"].lower() or "double-check" in res["reply"].lower()
