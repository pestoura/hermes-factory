from dataclasses import dataclass
from enum import StrEnum


class FindingClass(StrEnum):
    IMPLEMENTATION_DEFECT = "IMPLEMENTATION_DEFECT"
    TEST_DEFECT = "TEST_DEFECT"
    REQUIREMENT_DEFECT = "REQUIREMENT_DEFECT"
    ARCHITECTURE_DEFECT = "ARCHITECTURE_DEFECT"
    SECURITY_DEFECT = "SECURITY_DEFECT"
    PLATFORM_DEFECT = "PLATFORM_DEFECT"
    CONFIGURATION_DEFECT = "CONFIGURATION_DEFECT"
    ENVIRONMENT_DEFECT = "ENVIRONMENT_DEFECT"
    TEST_DATA_DEFECT = "TEST_DATA_DEFECT"
    DOCUMENTATION_DEFECT = "DOCUMENTATION_DEFECT"
    DEPENDENCY_DEFECT = "DEPENDENCY_DEFECT"
    PRODUCT_DECISION_REQUIRED = "PRODUCT_DECISION_REQUIRED"
    EXTERNAL_BLOCKER = "EXTERNAL_BLOCKER"


class ReworkState(StrEnum):
    REWORK_ALLOWED = "REWORK_ALLOWED"
    ESCALATE_DIAGNOSIS = "ESCALATE_DIAGNOSIS"
    HITL_REQUIRED = "HITL_REQUIRED"


@dataclass(frozen=True)
class Finding:
    finding_id: str
    classification: FindingClass
    same_cause_attempts: int


class ReworkController:
    def __init__(self, max_same_cause_attempts: int) -> None:
        if max_same_cause_attempts < 1:
            raise ValueError("max_same_cause_attempts must be >= 1")
        self.max_same_cause_attempts = max_same_cause_attempts

    def next_state(self, finding: Finding) -> ReworkState:
        if finding.classification is FindingClass.PRODUCT_DECISION_REQUIRED:
            return ReworkState.HITL_REQUIRED
        if finding.same_cause_attempts >= self.max_same_cause_attempts:
            return ReworkState.ESCALATE_DIAGNOSIS
        return ReworkState.REWORK_ALLOWED
