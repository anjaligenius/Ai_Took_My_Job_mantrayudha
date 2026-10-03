import re
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from src.policy.engine import parse_date
from src.risk.models import RiskEvaluation

LEGAL_KEYWORDS = [
    r"\bsue\b",
    r"\blawyer\b",
    r"\bcourt\b",
    r"\bconsumer\s*(?:court|forum)\b",
    r"\blegal\s*(?:action|notice)\b",
    r"\bpolice\b",
    r"\bfir\b",
]

SAFETY_KEYWORDS = [
    r"\bswelling\b",
    r"\bswollen\b",
    r"\bbulge\b",
    r"\bbulging\b",
    r"\bsmoke\b",
    r"\bspark\b",
    r"\bexplosion\b",
    r"\bburned\b",
    r"\bfire\b",
    r"\boverheating\b",
]

DIFFERENT_DESTINATION_KEYWORDS = [
    r"\bdifferent\s*(?:account|card|upi|bank)\b",
    r"\banother\s*(?:account|card|upi|bank)\b",
    r"\bfriend(?:'s)?\s*(?:account|card|upi|bank)\b",
    r"\bwife(?:'s)?\s*(?:account|card|upi|bank)\b",
    r"\bhusband(?:'s)?\s*(?:account|card|upi|bank)\b",
]

INJECTION_KEYWORDS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"override\s+(?:all\s+)?(?:system|developer|safety)\s+(?:rules|prompts|instructions|checks)",
    r"system\s*prompt",
    r"developer\s*(?:mode|instructions)",
    r"reveal\s+(?:your\s+)?(?:system\s+)?(?:instructions|prompt|database)",
    r"you\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|admin|developer|root)",
    r"jailbreak",
]


def detect_risk_signals(
    customer_message: str,
    customer=None,
    order=None,
    recent_tickets: Optional[List] = None,
    requested_amount: Optional[float] = None,
    target_customer_id: Optional[str] = None,
) -> RiskEvaluation:
    signals: List[str] = []
    msg = customer_message.lower()

    # 0. Prompt injection / adversarial input
    for pat in INJECTION_KEYWORDS:
        if re.search(pat, msg):
            signals.append("prompt_injection")
            return RiskEvaluation(
                risk_level="HIGH",
                signals=signals,
                requires_escalation=True,
                escalation_team="Trust & Safety",
                escalation_reason="Adversarial prompt injection attempt detected.",
            )

    # 1. Safety incident
    for pat in SAFETY_KEYWORDS:
        if re.search(pat, msg):
            signals.append("product_safety_incident")
            return RiskEvaluation(
                risk_level="CRITICAL",
                signals=signals,
                requires_escalation=True,
                escalation_team="Technical Support",
                escalation_reason="Device safety hazard detected in customer message.",
            )

    # 2. Legal threats
    for pat in LEGAL_KEYWORDS:
        if re.search(pat, msg):
            signals.append("legal_threat")
            return RiskEvaluation(
                risk_level="HIGH",
                signals=signals,
                requires_escalation=True,
                escalation_team="Customer Experience",
                escalation_reason="Legal threat language detected in customer message.",
            )

    # 3. Account suspended
    if customer and getattr(customer, "account_status", "").lower() == "suspended":
        signals.append("account_suspended")
        return RiskEvaluation(
            risk_level="HIGH",
            signals=signals,
            requires_escalation=True,
            escalation_team="Trust & Safety",
            escalation_reason="Customer account is suspended.",
        )

    # 4. Unauthorized order ownership
    if order and target_customer_id:
        if order.customer_id != target_customer_id:
            signals.append("unauthorized_order_access")
            return RiskEvaluation(
                risk_level="HIGH",
                signals=signals,
                requires_escalation=True,
                escalation_team="Trust & Safety",
                escalation_reason="Customer attempted to access/modify an order belonging to another customer.",
            )

    # 5. Delivery dispute / Contradictory claim: customer claims not delivered, but DB says delivered
    if order:
        deliv_status = (getattr(order, "delivery_status", "") or "").lower()
        order_status = (getattr(order, "order_status", "") or "").lower()
        if deliv_status == "delivered" or order_status == "delivered":
            if any(p in msg for p in ["not received", "never received", "didn't receive", "not delivered", "haven't received"]):
                has_otp = bool(getattr(order, "delivery_otp_verified", False))
                sig = "contradictory_otp_claim" if has_otp else "disputed_delivery_claim"
                signals.append(sig)
                return RiskEvaluation(
                    risk_level="HIGH",
                    signals=signals,
                    requires_escalation=True,
                    escalation_team="Logistics Desk",
                    escalation_reason=(
                        "Customer claims non-delivery for an OTP-verified delivered order."
                        if has_otp
                        else "Customer disputes delivery for an order marked delivered in records."
                    ),
                )

    # 6. Refund destination mismatch
    for pat in DIFFERENT_DESTINATION_KEYWORDS:
        if re.search(pat, msg):
            signals.append("refund_destination_mismatch")
            return RiskEvaluation(
                risk_level="MEDIUM",
                signals=signals,
                requires_escalation=True,
                escalation_team="Refunds & Payments",
                escalation_reason="Customer requested refund to an alternate non-original account.",
            )

    # 7. Repeated claims in last 90 days (>= 3)
    if recent_tickets:
        claim_categories = {"refund", "return", "delivery_issue", "missing_item"}
        ninety_days_claims = 0
        for t in recent_tickets:
            cat = (getattr(t, "category", "") or "").lower()
            if any(c in cat for c in claim_categories):
                ninety_days_claims += 1
        if ninety_days_claims >= 3:
            signals.append("repeated_claims_90_days")
            return RiskEvaluation(
                risk_level="HIGH",
                signals=signals,
                requires_escalation=True,
                escalation_team="Trust & Safety",
                escalation_reason="Customer has 3 or more return/refund/delivery claims in the last 90 days.",
            )

    # 8. Excess refund claim
    if order and requested_amount is not None:
        order_total = getattr(order, "total_amount", 0.0)
        if requested_amount > order_total:
            signals.append("excess_refund_claim")

    # 9. High-value order approval threshold
    if order:
        order_total = getattr(order, "total_amount", 0.0)
        dt = parse_date(order.order_date)
        threshold = 75000.0 if dt and dt >= date(2026, 6, 1) else 100000.0
        if order_total > threshold:
            signals.append("high_value_order_threshold")

    risk_level = "MEDIUM" if signals else "LOW"
    return RiskEvaluation(
        risk_level=risk_level,
        signals=signals,
        requires_escalation=False,
    )
