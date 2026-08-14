from pathlib import Path

from handspan.schema.conditions import Condition
from handspan.surface.ax_compact import compact
from handspan.surface.base import Observation


def test_observation_text_present() -> None:
    obs = Observation(url="http://x", ax_text="No records found")
    assert obs.matches(Condition(kind="text_present", value="No records found"))
    assert not obs.matches(Condition(kind="text_present", value="Sub-account Confirmation"))


def test_ax_compact_caps_and_prefers_interactive() -> None:
    tree = {
        "nodes": [{"role": "StaticText", "name": "x"}] * 200 + [{"role": "button", "name": "Find"}]
    }
    out = compact(tree, cap=10)
    assert len(out) <= 10
    assert any(n["name"] == "Find" for n in out)


def test_no_sleep_in_handspan() -> None:
    root = Path("src/handspan")
    for p in root.rglob("*.py"):
        text = p.read_text()
        assert "time.sleep(" not in text, p
        assert "asyncio.sleep(" not in text, p


def test_replay_does_not_import_llm_or_discovery() -> None:
    root = Path("src/handspan/replay")
    for p in root.rglob("*.py"):
        text = p.read_text()
        assert "handspan.discovery" not in text, p
        assert "handspan.llm" not in text, p
