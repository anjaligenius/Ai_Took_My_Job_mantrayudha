from dataclasses import dataclass, field
from typing import List


@dataclass
class RiskEvaluation:
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    signals: List[str] = field(default_factory=list)
    requires_escalation: bool = False
    escalation_team: str | None = None
    escalation_reason: str | None = None
