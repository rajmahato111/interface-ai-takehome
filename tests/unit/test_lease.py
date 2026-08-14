from pathlib import Path

from pytest import raises

from handspan.errors.taxonomy import HardFailure
from handspan.session.lease import Lease, LeaseState


def test_lease_fsm_and_assert(tmp_path: Path) -> None:
    lease = Lease(tmp_path / "lease.json", "sess1")
    lease.start()
    assert lease.state() == LeaseState.AUTOMATION_HELD
    lease.assert_automation()
    lease.transition(LeaseState.PAUSE_REQUESTED)
    with raises(HardFailure):
        lease.assert_automation()
    lease.transition(LeaseState.HUMAN_HELD)
    lease.transition(LeaseState.RESUME_REQUESTED)
    lease.transition(LeaseState.AUTOMATION_HELD)
    lease.assert_automation()


def test_illegal_transition(tmp_path: Path) -> None:
    lease = Lease(tmp_path / "lease.json", "sess1")
    lease.start()
    with raises(HardFailure):
        lease.transition(LeaseState.HUMAN_HELD)
