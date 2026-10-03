from typing import Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field

DecisionType = Literal["ANSWER", "ASK", "ACT", "ESCALATE"]


class IntentItem(BaseModel):
    intent: str  # order_status, refund, return, cancel, warranty, payment, faq, escalation
    order_id: Optional[str] = None
    product_name: Optional[str] = None
    reason: Optional[str] = None
    requested_amount: Optional[float] = None
    details: Optional[str] = None


class TraceItem(BaseModel):
    agent: str
    tool: str
    args: Dict[str, Any]
    result: Any


class AgentState(TypedDict, total=False):
    # Input & context
    user_message: str
    customer_id: Optional[str]
    session_id: Optional[str]
    history: List[Any]
    current_date: Optional[str]  # Simulated date context (default today)

    # Context loaded from authoritative DB
    customer_profile: Optional[Dict[str, Any]]
    customer_orders: List[Dict[str, Any]]
    customer_tickets: List[Dict[str, Any]]

    # Step 1: Understand & Decompose
    identified_intents: List[Dict[str, Any]]
    is_adversarial: bool
    ambiguity_detected: bool
    ambiguity_question: Optional[str]

    # Step 2: Verification against DB
    verified_facts: Dict[str, Any]
    active_order_id: Optional[str]
    order_verified: bool
    customer_verified: bool

    # Step 3: Policy & Risk Evaluation
    applicable_policies: List[Dict[str, Any]]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    risk_signals: List[str]
    requires_escalation: bool
    escalation_team: Optional[str]
    escalation_reason: Optional[str]

    # Step 4: Decision Gate
    decision: DecisionType  # ANSWER, ASK, ACT, ESCALATE
    missing_information: Optional[str]

    # Step 5: Action & Verification
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    action_result: Optional[Dict[str, Any]]
    action_verified: bool

    # Output & telemetry
    final_response: str
    reply: str
    trace: List[Dict[str, Any]]
    agent: str
    usage: Dict[str, int]
    cached: bool
