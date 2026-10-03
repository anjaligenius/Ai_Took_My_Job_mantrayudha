from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass
class PolicyRuleSet:
    policy_type: str  # refund, return, cancellation, warranty, shipping, payment
    version: str  # v1, v2, 1.0
    effective_from: str
    effective_to: Optional[str]
    change_of_mind_window_days: int
    defect_window_days: int
    approval_threshold: Decimal
    restocking_fee_rate: Decimal
    restocking_fee_cap: Decimal
    restocking_categories: List[str] = field(default_factory=list)
    loyalty_extensions: dict = field(default_factory=lambda: {"gold": 2, "platinum": 3})
    gst_rate: Decimal = Decimal("0.18")


class DictAccessMixin:
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return hasattr(self, key)


@dataclass
class RefundEligibilityResult(DictAccessMixin):
    eligible: bool
    reason: str
    policy_version: str
    reason_code: str
    max_refund_amount: Decimal = Decimal("0.00")
    item_refund_amount: Decimal = Decimal("0.00")
    shipping_refund_amount: Decimal = Decimal("0.00")
    restocking_fee: Decimal = Decimal("0.00")
    requires_human_approval: bool = False
    escalation_team: Optional[str] = None
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class ReturnEligibilityResult(DictAccessMixin):
    eligible: bool
    reason: str
    policy_version: str
    reason_code: str
    window_days: int
    days_since_delivery: Optional[int]
    requires_human_approval: bool = False
    remedy: str = "refund"  # refund, replacement, warranty
    escalation_team: Optional[str] = None


@dataclass
class WarrantyEligibilityResult(DictAccessMixin):
    eligible: bool
    status: str  # active, expired, not_covered, in_defect_window
    reason: str
    warranty_months: int
    expiry_date: Optional[str]
    days_remaining: int = 0
    remedy: str = "warranty_service"  # return_refund, warranty_service, paid_repair, safety_escalate
    requires_human: bool = False


@dataclass
class CancellationEligibilityResult(DictAccessMixin):
    eligible: bool
    reason: str
    order_status: str
    refund_applicable: bool
    refund_amount: Decimal = Decimal("0.00")
