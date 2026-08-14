# ADR-002 — Computer-use: Playwright + accessibility tree

## Decision
Playwright (Chromium, persistent context) is the transport. The accessibility tree is the primary perception channel; screenshot is secondary; DOM is last.

## Why
The brief wants an approach that survives with no clean DOM. Artifacts record semantic targets, not markup. Playwright also gives frames (framesets), CDP (live handoff), and traces (evidence).

## Trade-off
Not OS-level. A native desktop app needs a new `Surface` adapter. The port is defined so that adapter is additive.
