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


def test_physical_damage_excluded_from_warranty():
    # Customer reports cracked screen from dropping phone
    res = tools.check_warranty_eligibility(
        order_id="ORD-000001",
        issue_description="I dropped my device and the screen cracked into pieces",
        current_date="2026-05-01",
    )
    assert res["eligible"] is False
    assert res["status"] == "not_covered"
    assert res["remedy"] == "paid_repair"


def test_active_warranty_eligible():
    # Normal manufacturing defect reported during active warranty (delivered 2026-04-15, 12 months warranty)
    res = tools.check_warranty_eligibility(
        order_id="ORD-000001",
        issue_description="Audio has stopped playing from the left ear piece under normal use",
        current_date="2026-07-01",
    )
    assert res["eligible"] is True
    assert res["status"] == "active"
    assert res["days_remaining"] > 0
    assert res["remedy"] == "warranty_service"


def test_safety_hazard_triggers_safety_escalation():
    res = tools.check_warranty_eligibility(
        order_id="ORD-000001",
        issue_description="Battery is swelling and smoking while charging",
    )
    assert res["requires_human"] is True
    assert res["status"] == "safety_hazard"
    assert res["remedy"] == "safety_escalate"
