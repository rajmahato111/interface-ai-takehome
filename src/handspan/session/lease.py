"""Single-holder session lease. Executor checks before every action."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from handspan.errors.taxonomy import Code, HardFailure

# ponytail: file lock via atomic replace, Redis if more than one process needs the lease


class LeaseState(StrEnum):
    AUTOMATION_HELD = "AUTOMATION_HELD"
    PAUSE_REQUESTED = "PAUSE_REQUESTED"
    HUMAN_HELD = "HUMAN_HELD"
    RESUME_REQUESTED = "RESUME_REQUESTED"
    TERMINATED = "TERMINATED"


_ALLOWED: dict[LeaseState, set[LeaseState]] = {
    LeaseState.AUTOMATION_HELD: {LeaseState.PAUSE_REQUESTED, LeaseState.TERMINATED},
    LeaseState.PAUSE_REQUESTED: {LeaseState.HUMAN_HELD, LeaseState.TERMINATED},
    LeaseState.HUMAN_HELD: {LeaseState.RESUME_REQUESTED, LeaseState.TERMINATED},
    LeaseState.RESUME_REQUESTED: {LeaseState.AUTOMATION_HELD, LeaseState.TERMINATED},
    LeaseState.TERMINATED: set(),
}


class Lease:
    def __init__(self, path: Path, session_id: str) -> None:
        self.path = path
        self.session_id = session_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        self._write(
            {
                "session_id": self.session_id,
                "state": LeaseState.AUTOMATION_HELD.value,
                "holder": "automation",
            }
        )

    def state(self) -> LeaseState:
        return LeaseState(self._read()["state"])

    def holder(self) -> str:
        return str(self._read().get("holder") or "")

    def assert_automation(self) -> None:
        st = self.state()
        if st != LeaseState.AUTOMATION_HELD:
            raise HardFailure(Code.LEASE_NOT_HELD, f"lease is {st.value}, automation cannot act")

    def transition(self, dest: LeaseState, *, holder: str | None = None) -> None:
        data = self._read()
        cur = LeaseState(data["state"])
        if dest not in _ALLOWED[cur]:
            raise HardFailure(Code.LEASE_NOT_HELD, f"illegal lease {cur.value} → {dest.value}")
        data["state"] = dest.value
        if holder is not None:
            data["holder"] = holder
        elif dest == LeaseState.HUMAN_HELD:
            data["holder"] = "human"
        elif dest == LeaseState.AUTOMATION_HELD:
            data["holder"] = "automation"
        self._write(data)

    def wait_for(self, dest: LeaseState, timeout_s: float = 900.0) -> bool:
        """Block until state==dest or TERMINATED. Uses Event.wait, not sleep()."""
        import threading
        import time

        deadline = time.monotonic() + timeout_s
        ev = threading.Event()
        # ponytail: poll file mtime via Event.wait slices; inotify if this is hot
        while time.monotonic() < deadline:
            st = self.state()
            if st == dest:
                return True
            if st == LeaseState.TERMINATED:
                return False
            ev.wait(0.25)
        return False

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "session_id": self.session_id,
                "state": LeaseState.TERMINATED.value,
                "holder": "",
            }
        return json.loads(self.path.read_text())

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)
