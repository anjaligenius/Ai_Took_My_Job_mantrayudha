from langchain_core.tools import tool

from src import tools as backend_tools
from src.agents.base import run_tool_agent


@tool
def check_refund_eligibility(order_id: str, reason: str = "change_of_mind") -> dict:
    """Check whether an order is eligible for a refund under versioned policy (window, returnability, delivery status)."""
    return backend_tools.check_refund_eligibility(order_id, reason=reason)


@tool
def calculate_refund(order_id: str, reason: str = "change_of_mind") -> dict:
    """Calculate exact refundable amount including 18% GST and deducting restocking fee if applicable under v2."""
    return backend_tools.calculate_refund(order_id, reason=reason)


@tool
def create_refund(order_id: str, amount: float, reason: str) -> dict:
    """Process an approved refund for an order within agent authority limit. MODIFIES STATE."""
    return backend_tools.create_refund(order_id=order_id, amount=amount, reason=reason)


@tool
def check_return_eligibility(order_id: str, reason: str = "change_of_mind") -> dict:
    """Check whether an item is eligible for physical return."""
    return backend_tools.check_return_eligibility(order_id, reason=reason)


@tool
def create_return(order_id: str, reason: str) -> dict:
    """Initiate a return pickup request for eligible items. MODIFIES STATE."""
    return backend_tools.create_return(order_id=order_id, reason=reason)


@tool
def check_delivery_claim(order_id: str, customer_statement: str) -> dict:
    """Verify customer non-delivery claims against OTP delivery confirmation in the database."""
    return backend_tools.check_delivery_claim(order_id, customer_statement)


REFUND_TOOLS = [
    check_refund_eligibility,
    calculate_refund,
    create_refund,
    check_return_eligibility,
    create_return,
    check_delivery_claim,
]

SYSTEM_PROMPT = (
    "You are the Refund & Return Agent for NovaMart customer support.\n"
    "CRITICAL RULES:\n"
    "1. Never invent refund amounts or approve requests outside the policy window.\n"
    "2. Applicable policy version is determined by order placement date (v1 before June 1 2026, v2 on/after June 1 2026).\n"
    "3. Orders exceeding the approval threshold (v1: ₹1,00,000, v2: ₹75,000) CANNOT be approved by AI; escalate to human.\n"
    "4. If an order was OTP-verified as delivered, do NOT issue an automatic refund for non-delivery; escalate to Logistics Desk.\n"
    "5. If customer requests an amount higher than the order value, cap it to the maximum valid refund amount.\n"
    "Always check eligibility before initiating any action."
)


def run_refund_agent(user_message: str, history: list | None = None) -> dict:
    return run_tool_agent("refund", SYSTEM_PROMPT, REFUND_TOOLS, user_message, history)
