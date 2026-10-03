import pytest
from src.backend.db import get_engine, get_session_factory, Product
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


def test_get_product_specs_valid():
    """Verify authoritative spec sheet retrieval for valid products."""
    res_cam = tools.get_product_specs("PROD-00035")
    assert res_cam["found"] is True
    assert res_cam["product_id"] == "PROD-00035"
    assert "2100 mAh" in res_cam["specifications"]
    assert "1/2.3-inch 12 MP" in res_cam["specifications"]

    res_laptop = tools.get_product_specs("PROD-00050")
    assert res_laptop["found"] is True
    assert res_laptop["product_id"] == "PROD-00050"
    assert "Helix" in res_laptop["specifications"] or "Warranty" in res_laptop["specifications"]


def test_get_product_specs_invalid():
    """Verify non-existent product returns found=False without hallucinating."""
    res = tools.get_product_specs("PROD-99999")
    assert res["found"] is False
    assert "not found" in res["error"].lower()


def test_get_product_specs_fallback_when_spec_missing():
    """Verify missing spec sheet returns 'specification unavailable' rather than invented values."""
    with tools._session() as s:
        p = Product(
            product_id="PROD-88888",
            sku="TEST-SKU-88888",
            product_name="Unspecified Gadget",
            category="electronics",
            subcategory="Gadgets",
            brand="Generic",
            description="A test gadget",
            price=1999.0,
            mrp=2499.0,
            color="Black",
            status="active",
            spec_sheet_md=None,
        )
        s.add(p)
        s.commit()

    res = tools.get_product_specs("PROD-88888")
    assert res["found"] is True
    assert res["specifications"] == "specification unavailable"


def test_orchestrator_answers_spec_query():
    """Verify orchestrator answers user spec questions with authoritative details."""
    res = run_orchestrator(
        user_message="What are the technical specifications and battery for PROD-00035?",
        customer_id="CUST-00001",
    )
    assert res["decision"] == "ANSWER"
    assert res["agent"] == "order"
    assert "PROD-00035" in res["reply"]
    assert "2100 mAh" in res["reply"]


def test_orchestrator_product_spec_from_order():
    """Verify orchestrator looks up order item product when user asks for specs in an order."""
    res = run_orchestrator(
        user_message="What are the specs of the item in ORD-000001?",
        customer_id="CUST-00001",
    )
    assert res["decision"] == "ANSWER"
    assert "PROD-00001" in res["reply"] or "Voltix" in res["reply"]


def test_orchestrator_spec_and_tracking_combined():
    """Verify multi-intent query with product specs + delivery tracking returns combined answer."""
    res = run_orchestrator(
        user_message="What are the specs for PROD-00035 and where is my order ORD-000001?",
        customer_id="CUST-00001",
    )
    assert res["decision"] == "ANSWER"
    assert "PROD-00035" in res["reply"]
    assert "delivery status" in res["reply"].lower() or "delivered" in res["reply"].lower()
