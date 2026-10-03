from langchain_core.tools import tool

from src import tools as backend_tools
from src.agents.base import run_tool_agent


@tool
def check_payment_status(order_id: str) -> dict:
    """Look up the payment status (pending/paid/refunded) and payment method for an order."""
    return backend_tools.check_payment_status(order_id)


@tool
def process_payment(order_id: str, method: str) -> dict:
    """Process a pending payment for an order using the given method (e.g. 'upi', 'credit_card')."""
    return backend_tools.process_payment(order_id, method)


PAYMENT_TOOLS = [check_payment_status, process_payment]

SYSTEM_PROMPT = (
    "You are the Payment Agent for NovaMart customer support.\n"
    "RULES:\n"
    "1. You can check payment status and process pending payments.\n"
    "2. Refunds are ONLY permitted to the original payment instrument; never accept requests to refund to an alternate card/UPI in chat.\n"
    "3. Only process a payment that is currently pending; if it's already paid or refunded, explain that instead.\n"
    "4. If unconfirmed payment is pending under 24 hours, advise waiting for bank confirmation.\n"
    "Reply concisely and accurately."
)


def run_payment_agent(user_message: str, history: list | None = None) -> dict:
    return run_tool_agent("payment", SYSTEM_PROMPT, PAYMENT_TOOLS, user_message, history)
