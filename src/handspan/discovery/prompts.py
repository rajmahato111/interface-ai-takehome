SYSTEM = """You operate a legacy credit-union servicing console through a closed action vocabulary.
You see a compacted accessibility tree, never raw HTML. Prefer role+accessible name.
When a value came from the goal, pass value_from_input instead of a literal (member_id, not 100234).
Fill each field once. If the member ID is already in the search box, click Find (or Search).
After you have extracted the requested fields, call finish immediately. Do not extract or type the same thing twice.
Escalate if stuck. Never type credentials after a session timeout.
"""


def user_prompt(
    goal: str,
    obs_text: str,
    ax: list,
    url: str,
    remaining: int,
    got: dict | None = None,
    history: list[str] | None = None,
) -> str:
    got = got or {}
    extra = f"ALREADY_EXTRACTED: {got}\n" if got else ""
    hist = f"RECENT: {history[-5:]}\n" if history else ""
    return (
        f"GOAL: {goal}\nURL: {url}\nSTEPS_LEFT: {remaining}\n{extra}{hist}"
        f"AX:\n{ax}\nVISIBLE TEXT (truncated):\n{obs_text[:4000]}\n"
        "Call exactly one tool. If ALREADY_EXTRACTED covers the goal, call finish."
        " If the member ID is already filled, click Find."
    )
