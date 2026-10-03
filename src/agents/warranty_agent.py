from langchain_core.tools import tool

from src import tools as backend_tools
from src.agents.base import run_tool_agent


@tool
def get_product(product_id_or_sku: str) -> dict:
    """Fetch product specifications, brand, warranty duration, and returnability."""
    return backend_tools.get_product(product_id_or_sku)


@tool
def check_warranty_eligibility(order_id: str, issue_description: str, product_id: str | None = None) -> dict:
    """Check whether a product issue is covered under warranty vs expired vs physical damage."""
    return backend_tools.check_warranty_eligibility(order_id, issue_description, product_id=product_id)


@tool
def create_support_ticket(customer_id: str, issue_summary: str, order_id: str | None = None) -> dict:
    """Register a warranty claim or service ticket."""
    return backend_tools.create_support_ticket(
        customer_id=customer_id,
        category="warranty",
        subcategory="claim",
        issue_summary=issue_summary,
        order_id=order_id,
    )


WARRANTY_TOOLS = [get_product, check_warranty_eligibility, create_support_ticket]

SYSTEM_PROMPT = (
    "You are the Product & Warranty Agent for NovaMart customer support.\n"
    "RULES:\n"
    "1. Physical damage (drops, cracked screens) and liquid damage are NOT covered under warranty. Offer paid repair options.\n"
    "2. If safety symptoms (swelling battery, smoke, overheating) are reported, instruct the customer to disconnect and stop using immediately and escalate.\n"
    "3. Inside the defect window (15 days v1 / 10 days v2), refer to refund/return policy. Beyond the defect window but within warranty duration, provide warranty service (repair/replacement).\n"
    "4. Beyond warranty expiry, offer paid repair.\n"
    "Reply concisely and empathetically."
)


def run_warranty_agent(user_message: str, history: list | None = None) -> dict:
    return run_tool_agent("warranty", SYSTEM_PROMPT, WARRANTY_TOOLS, user_message, history)
