from decimal import Decimal
from src.policy.models import PolicyRuleSet

REFUND_RETURN_V1 = PolicyRuleSet(
    policy_type="refund_return",
    version="v1",
    effective_from="2026-01-01",
    effective_to="2026-05-31",
    change_of_mind_window_days=10,
    defect_window_days=15,
    approval_threshold=Decimal("100000.00"),
    restocking_fee_rate=Decimal("0.00"),
    restocking_fee_cap=Decimal("0.00"),
    restocking_categories=[],
    loyalty_extensions={"gold": 2, "platinum": 3},
    gst_rate=Decimal("0.18"),
)

REFUND_RETURN_V2 = PolicyRuleSet(
    policy_type="refund_return",
    version="v2",
    effective_from="2026-06-01",
    effective_to=None,
    change_of_mind_window_days=7,
    defect_window_days=10,
    approval_threshold=Decimal("75000.00"),
    restocking_fee_rate=Decimal("0.05"),
    restocking_fee_cap=Decimal("2500.00"),
    restocking_categories=["laptops", "tablets", "cameras", "monitors"],
    loyalty_extensions={"gold": 2, "platinum": 3},
    gst_rate=Decimal("0.18"),
)
