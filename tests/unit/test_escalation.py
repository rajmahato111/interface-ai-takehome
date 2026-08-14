from pathlib import Path

from handspan.schema.conditions import Condition
from handspan.session.lease import Lease, LeaseState
from handspan.surface.base import Observation


def test_resume_state_mismatch_logic() -> None:
    obs = Observation(url="http://x", ax_text="totally wrong screen")
    need = Condition(kind="ax_present", name_matches="^Sub-account")
    assert not obs.matches(need)


def test_handoff_lease_file(tmp_path: Path) -> None:
    lease = Lease(tmp_path / "lease.json", "s")
    lease.start()
    lease.transition(LeaseState.PAUSE_REQUESTED)
    lease.transition(LeaseState.HUMAN_HELD)
    assert lease.state() == LeaseState.HUMAN_HELD
    lease.transition(LeaseState.RESUME_REQUESTED)
    lease.transition(LeaseState.AUTOMATION_HELD)
