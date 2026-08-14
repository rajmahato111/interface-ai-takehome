"""Locator strategy ladder. First unique match wins. Ambiguity is a failure."""

from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Frame, FrameLocator, Page

from handspan.errors.taxonomy import Code, HardFailure
from handspan.schema.capability import Strategy, Target
from handspan.surface.base import Handle


def frame_named(page: Page, name: str | None) -> Page | Frame | FrameLocator:
    if not name:
        return page
    for fr in page.frames:
        if fr.name == name:
            return fr
        if name == "nav" and "/servicing/nav" in (fr.url or ""):
            return fr
        if name == "content" and any(
            p in (fr.url or "")
            for p in ("/servicing/welcome", "/member/", "/subaccount/", "/servicing/postback")
        ):
            return fr
    loc = page.frame_locator(f"frame[name='{name}'], iframe[name='{name}']")
    try:
        loc.locator("body").wait_for(timeout=5000)
    except Exception:
        pass
    return loc


def resolve(page: Page, target: Target) -> Handle:
    scope = frame_named(page, target.frame)
    last_err = "no strategies"
    ambiguous = False
    for i, strat in enumerate(target.strategies, start=1):
        try:
            locs = _find(scope, strat)
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            continue
        if not locs:
            continue
        if target.match_policy == "require_unique" and len(locs) > 1:
            ambiguous = True
            last_err = (
                f"{len(locs)} matches for {strat.kind}:{strat.name or strat.label or strat.value}"
            )
            continue
        idx = (target.nth - 1) if target.match_policy == "nth" else 0
        loc = locs[min(idx, len(locs) - 1)]
        if isinstance(loc, Handle):
            loc.rung = i
            loc.frame_name = target.frame
            return loc
        if strat.kind == "visual_anchor" and isinstance(loc, tuple):
            return Handle(rung=i, locator=None, frame_name=target.frame, click_point=loc)
        return Handle(rung=i, locator=loc, frame_name=target.frame)
    if ambiguous:
        raise HardFailure(Code.AMBIGUOUS_TARGET, last_err)
    raise HardFailure(Code.LOCATOR_EXHAUSTED, last_err)


def _names(strat: Strategy) -> list[str]:
    names = [strat.name] if strat.name else []
    if strat.aliases:
        names.extend(strat.aliases)
    if strat.label:
        names.append(strat.label)
    if strat.label_text:
        names.append(strat.label_text)
    if strat.anchor_text:
        names.append(strat.anchor_text)
    return [n for n in names if n]


def _find(scope: Page | Frame | FrameLocator, strat: Strategy) -> list[Any]:
    kind = strat.kind
    if kind == "ax_role_name":
        return _by_role(scope, strat)
    if kind == "ax_label_proximity":
        return _by_label_td(scope, strat.label or strat.name or "", strat.direction or "right")
    if kind == "table_cell_neighbour":
        label = strat.label_text or strat.label or strat.name or ""
        off = strat.cell_offset or [0, 1]
        return _by_table_offset(scope, label, off[0], off[1])
    if kind == "css":
        loc = scope.locator(strat.value or "")
        n = loc.count()
        return [loc.nth(i) for i in range(n)]
    if kind == "xpath":
        loc = scope.locator(f"xpath={strat.value}")
        n = loc.count()
        return [loc.nth(i) for i in range(n)]
    if kind == "visual_anchor":
        return _visual(scope, strat)
    if kind == "regex_in_region":
        return _regex_region(scope, strat)
    return []


def _by_role(scope: Page | Frame | FrameLocator, strat: Strategy) -> list[Any]:
    role = strat.role or "generic"
    found: list[Any] = []
    for name in _names(strat) or [None]:
        kwargs: dict[str, Any] = {}
        if name:
            if strat.match == "exact":
                kwargs["name"] = name
                kwargs["exact"] = True
            else:
                kwargs["name"] = re.compile(re.escape(name), re.I)
        loc = scope.get_by_role(role, **kwargs)
        n = loc.count()
        found.extend([loc.nth(i) for i in range(n)])
    return found


def _by_label_td(scope: Page | Frame | FrameLocator, label: str, direction: str) -> list[Any]:
    tds = scope.locator("td")
    n = tds.count()
    out: list[Any] = []
    for i in range(n):
        text = tds.nth(i).inner_text(timeout=1000).strip()
        if text.lower() != label.lower():
            continue
        neighbor = i + 1 if direction in {"right", "next"} else i - 1
        if 0 <= neighbor < n:
            inp = tds.nth(neighbor).locator(
                "input:not([type=submit]):not([type=button]), select, textarea"
            )
            if inp.count():
                out.append(inp.first)
            else:
                ntext = tds.nth(neighbor).inner_text(timeout=1000).strip()
                if ntext.lower() == label.lower():
                    continue
                out.append(tds.nth(neighbor))
    return out


def _by_table_offset(
    scope: Page | Frame | FrameLocator, label: str, row_off: int, col_off: int
) -> list[Any]:
    # ponytail: treat td list as a raster; good enough for the frozen nested-table markup
    if row_off == 0 and col_off == 1:
        return _by_label_td(scope, label, "right")
    if row_off == 1 and col_off == 0:
        tds = scope.locator("td")
        n = tds.count()
        for i in range(n):
            if label.lower() in tds.nth(i).inner_text(timeout=1000).strip().lower():
                j = i + 1
                if j < n:
                    inp = tds.nth(j).locator("input, select, textarea, button")
                    return [inp.first] if inp.count() else [tds.nth(j)]
        return []
    return _by_label_td(scope, label, "right")


def _visual(scope: Page | Frame | FrameLocator, strat: Strategy) -> list[Any]:
    text = strat.anchor_text or strat.name or ""
    loc = scope.get_by_text(text, exact=False)
    if loc.count() == 0:
        return []
    box = loc.first.bounding_box()
    if not box:
        return [loc.first]
    ox, oy = (strat.offset or [0, 0])[0], (strat.offset or [0, 0] + [0])[1] if strat.offset else 0
    if strat.offset:
        ox, oy = strat.offset[0], strat.offset[1] if len(strat.offset) > 1 else 0
    else:
        ox = oy = 0
    return [(box["x"] + box["width"] / 2 + ox, box["y"] + box["height"] / 2 + oy)]


def _regex_region(scope: Page | Frame | FrameLocator, strat: Strategy) -> list[Any]:
    anchor = strat.region_anchor or ""
    pat = re.compile(strat.pattern or "")
    blob = scope.locator("body").inner_text(timeout=2000)
    if anchor and anchor.lower() not in blob.lower():
        return []
    m = pat.search(blob)
    if not m:
        return []
    handle = Handle(rung=0, locator=None, extracted=m.group(0))
    return [handle]
