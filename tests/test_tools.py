import pytest

from src import tools
from src.backend.db import get_engine, get_session_factory
from src.backend.seed import seed


@pytest.fixture(autouse=True)
def seeded_db():
    engine = get_engine("sqlite:///:memory:")
    tools.configure_db(engine)
    session = get_session_factory(engine)()
    seed(session)
    yield


def test_get_order_status_found():
    res = tools.get_order_status("ORD-000001")
    assert res == {"order_id": "ORD-000001", "status": "delivered"}


def test_get_order_status_not_found():
    result = tools.get_order_status("ORD-999999")
    assert "error" in result


def test_get_order_details():
    result = tools.get_order_details("ORD-000001")
    assert result["customer_name"] == "Ravi Ali"
    assert result["status"] == "delivered"


def test_track_shipment_delivered():
    result = tools.track_shipment("ORD-000001")
    assert "Delivered" in result["tracking_message"]


def test_refund_eligibility_delivered_no_existing_refund():
    # ORD-000001 delivered on 2026-04-15; test request on 2026-04-18 (day 3 within 10-day v1 window)
    result = tools.check_refund_eligibility("ORD-000001", current_date="2026-04-18")
    assert result["eligible"] is True
    assert result["policy_version"] == "v1"


def test_refund_eligibility_not_delivered():
    result = tools.check_refund_eligibility("ORD-000002")  # shipped
    assert result["eligible"] is False
    assert "not delivered" in result["reason"].lower()


def test_refund_eligibility_window_expired():
    # Request made on 2026-05-10 for delivery on 2026-04-15 (day 25 > 10 days)
    result = tools.check_refund_eligibility("ORD-000001", current_date="2026-05-10")
    assert result["eligible"] is False
    assert "exceeding" in result["reason"].lower()


def test_initiate_refund_succeeds_when_eligible():
    result = tools.initiate_refund("ORD-000001", "Item defective", current_date="2026-04-18")
    assert result["success"] is True
    assert result["status"] == "requested"
    assert result.get("verified") is True


def test_initiate_refund_refuses_when_not_delivered():
    result = tools.initiate_refund("ORD-000002", "Changed my mind")
    assert result["success"] is False


def test_get_payment_status():
    result = tools.get_payment_status("ORD-000003")
    assert result["status"] == "pending"


def test_process_payment_succeeds_when_pending():
    result = tools.process_payment("ORD-000003", "upi")
    assert result["success"] is True
    assert tools.get_payment_status("ORD-000003")["status"] == "paid"


def test_process_payment_refuses_when_already_paid():
    result = tools.process_payment("ORD-000001", "credit_card")
    assert result["success"] is False


def test_answer_faq_shipping():
    answer = tools.answer_faq("How long does shipping take?")
    assert "3-5" in answer or "shipping" in answer.lower()


def test_escalate_to_human():
    result = tools.escalate_to_human("agent could not resolve", "user asked about order 9999")
    assert result["escalated"] is True
    assert "ticket_id" in result


def test_calculate_refund_gst_arithmetic():
    # Item final price = 2499.0, GST (18%) = 449.82, Total = 2948.82
    calc = tools.calculate_refund("ORD-000001")
    assert calc["item_final_price"] == 2499.0
    assert calc["gst_amount"] == 449.82
    assert calc["net_refund_amount"] == 2948.82


def test_check_delivery_claim_otp_contradiction():
    # ORD-000001 was delivered and OTP verified
    claim = tools.check_delivery_claim("ORD-000001", "I never received my package")
    assert claim["contradiction"] is True
    assert claim["action"] == "ESCALATE"
    assert claim["escalation_team"] == "Logistics Desk"


def test_check_cancellation_eligibility():
    # ORD-000003 is placed (unshipped)
    res = tools.check_cancellation_eligibility("ORD-000003")
    assert res["eligible"] is True
    assert res["refund_applicable"] is True
