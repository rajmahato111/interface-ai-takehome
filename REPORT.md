# REPORT

## 1. Design

Handspan is a compiler plus an interpreter. Discovery (LLM, tool-use, temperature 0) produces a typed YAML capability. Replay executes that YAML with no model in the loop. The two load-bearing seams are the `Surface` port (observation / resolve / act — no CSS above it) and the artifact (discovery's only output, replay's only input). `replay/` is import-banned from `discovery/` and `llm/`.

## 2. Discovery and recording

The agent sees a compacted accessibility tree, never HTML. Actions are a closed vocabulary shared with the executor. The compiler prunes no-ops, replaces literals with `from_input`, and emits a locator ladder per target. CI uses a cassette; `make discover-live` is the genuine LLM path when a key is present.

## 3. Replay and determinism

Replay binds params first (`INVALID_INPUT` fails before step 1), resolves a ranked locator ladder (`require_unique` — ambiguity is a failure), waits on conditions not sleeps, and classifies every unexpected screen into business outcome / recoverable / hard failure. Unknown is `UNEXPECTED_STATE`, never guessed success.

## 4. Heterogeneity and multi-tenant reuse

Ladder rungs 1 and 5 exist on every surface (AX/UIA name, then visual). Rungs 2–4 are web/legacy optimizations. Desktop would add a `Surface` adapter and window-based entry; the artifact schema does not change. Tenants are overlays (RFC-7386-style merge) on a base artifact keyed by `(product, product_version, capability_id)`. Overlays may patch targets and insert steps; they may not change `outputs`, `outcomes`, or `policy.risk_class`. Drift is `rung_used` inflation already logged on every replay.

## 5. Escalation and human control

A file-backed lease has one holder. The executor checks it before every action. Stuck, session expiry, and attended risky actions raise an `InterventionRequest` with a `resume_contract`. The human drives the same persistent Playwright context (bare window or the mock console). Resume re-verifies required state or fails `RESUME_STATE_MISMATCH`. Human actions are recorded, not auto-merged into approved artifacts.

## 6. Safety, policy, and data handling

Allowlist is a pre-flight gate on every action in both engines; post-navigation URL is checked again. Risky actions fail closed in unattended replay. Values never live in artifacts (`from_input` only). Logs are redacted before they hit a buffer. Screenshots are PII: sensitive AX regions are masked, evidence dirs are mode 0700. A corpus scanner test gates CI.

## 7. Cuts and next steps

| Cut | Why | Next |
|---|---|---|
| Desktop/UIA adapter | Port defined; Windows work for the same idea | UIA `Surface`, process allowlist |
| Real co-browse console | Brief: mechanism matters, UI does not | CDP-streamed console |
| Queues / Redis / catalog API | Brief penalises scaling infra | Executor as worker, lease in Redis |
| Credential vault | We never type secrets on expiry | Broker logs in, agent inherits session |
| Auto-promote human steps | Unreviewed edits to approved capabilities | Overlay PR with review |
