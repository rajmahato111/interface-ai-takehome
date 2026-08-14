"""Frozen hostility checklist. Do not edit to make an agent pass."""

HOSTILITY = """
- frameset with nav / content frames
- layout via nested tables; no main/section; no ARIA landmarks
- zero data-testid; ids like ctl00_mbrSrch_txt1, different prefix on tenant B
- labels adjacent in sibling td, not label-for
- navigation via javascript:__doPostBack and full page reloads
- server-rendered validation errors in a red span inside the form table
- session cookie with configurable idle expiry
- randomised server latency; ?fault= control plane
- tenant B: different brand CSS, field order, extra mandatory field, renamed button, different id prefix
"""
