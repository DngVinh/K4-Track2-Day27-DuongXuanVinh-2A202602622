from dataclasses import dataclass


@dataclass
class Verdict:
    alert: bool
    confidence: float = 1.0
    reason: str = ""
    pillar: str = ""
