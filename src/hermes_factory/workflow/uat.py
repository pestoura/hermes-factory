from dataclasses import dataclass
from enum import StrEnum

from hermes_factory.domain import UATState


class UATMode(StrEnum):
    AUTOMATED = "AUTOMATED"
    ASSISTED = "ASSISTED"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class UATExecution:
    scenario_id: str
    baseline_version: int
    mode: UATMode
    state: UATState
    candidate_revision: str | None

    def satisfies_acceptance(self) -> bool:
        if self.state is not UATState.PASS:
            return False
        if self.mode is UATMode.AUTOMATED and not self.candidate_revision:
            return False
        return True
