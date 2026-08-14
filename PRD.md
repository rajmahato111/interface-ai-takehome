# PRD — Computer-Use Automation System ("Handspan")

**Project:** interface.ai take-home — record-once / replay-many UI automation for legacy bank back-office apps
**Doc version:** 1.0
**Status:** Approved for build
**Owner:** Raj (acting as BA, Architect, Eng Lead, QA Lead, Security Lead)
**Codename:** `handspan` — *the agent-facing product decides what to do; Handspan is the hand that does it.*

---

## 0. How to read this document

| Section | Written from the seat of | Answers |
|---|---|---|
| 1–4 | Business Analyst | What problem, for whom, what counts as done |
| 5–7 | Technical Architect | Stack, boundaries, component design |
| 8–10 | Eng Lead (core) | Artifact schema, locator strategy, replay contract |
| 11–13 | Security Lead / Platform Lead | Guardrails, escalation, observability |
| 14 | Architect (design-only) | Heterogeneity + multi-tenant story |
| 15–18 | Eng Lead / QA Lead | Repo layout, test strategy, plan, risks |
| 19–21 | All | Acceptance criteria, cuts, appendices |

---

## 1. Executive summary

### 1.1 The problem in one paragraph

Banks and credit unions run a long tail of back-office applications with no API — core banking screens, servicing tools, admin consoles. The only integration surface is the UI a human operator drives. Using an LLM to drive that UI on every request is too slow, too expensive, and too non-deterministic for regulated production work. But a human writing selectors per app per tenant does not scale to hundreds of tenants × ~20 apps.

### 1.2 The solution shape

A three-phase lifecycle around a single durable object:

```
  DISCOVER                 RECORD                    REPLAY
  (LLM in the loop)        (artifact emitted)        (no LLM in the loop)
  goal + target      →     typed capability     →    agent calls capability(params)
  expensive, slow          reviewable, versioned     cheap, fast, deterministic
  once per flow            source of truth           thousands of times
                                  ↓
                          ESCALATE (human takes the live session, hands it back)
```

The **capability artifact** is the product. Discovery is how it gets written; replay is how it gets used; escalation is what happens when neither can finish safely.

### 1.3 Non-obvious decisions we are making up front

| Decision | Choice | Why |
|---|---|---|
| Target application | **Build a local "legacy" credit-union admin console** with a second tenant variant + fault injection | A public demo site cannot inject a session timeout, cannot be a second tenant, and cannot be re-run in CI. The brief's interesting problems live in the faults. |
| Perception surface | **Accessibility tree first, screenshot second, DOM last** | Brief explicitly says bias to approaches that survive with no clean DOM. AX tree also exists on desktop → the abstraction extends. |
| Locator model | **Ordered strategy ladder recorded per step, not a single selector** | A single selector is a single point of failure. The ladder doubles as a drift sensor: if rung 3 wins, rung 1 broke. |
| Result contract | **Four terminal states: `success` / `business_outcome` / `failed` / `escalated`** | The brief names conflating "no such member" with a crash as the most common design mistake. Make it structurally impossible. |
| Control transfer | **Explicit session lease with a single holder, enforced in the executor** | "Who is in control" must be a value in the system, not an implied state, or resume is unsafe. |
| Multi-tenant | **Base artifact + tenant overlay patch, resolved at load time** | Designed, not built. Prevents per-tenant re-recording without building tenant plumbing the brief says not to build. |

---

## 2. Context, scope, and constraints

### 2.1 Environment properties that drive design (from brief §1)

| Property | Design consequence |
|---|---|
| Stable UIs, real runtime errors | Optimise for **runtime error handling**, not for drift resilience. Error taxonomy is load-bearing; self-healing selectors are not. |
| Heterogeneous / legacy surfaces (framesets, table layouts, no test IDs) | Perception + action must be behind a `Surface` port. Locators must be semantic, not markup-coupled. Frame identity is a first-class part of a target. |
| Multi-tenant at scale (hundreds × ~20 apps, same vendor product) | Artifact identity is `(product, product_version)` — **not** `(tenant, app)`. Tenant is an overlay, not a copy. |
| Regulated financial data | Redaction at capture time, not at write time. Artifacts store *references to inputs*, never values. |

### 2.2 In scope (build)

Every core requirement from §3.1–3.6 of the brief, thin but real, end to end, with evidence.

### 2.3 In scope (design only, written in `REPORT.md`)

§3.7 — legacy web + desktop surface extension; cross-tenant artifact reuse and drift management.

### 2.4 Explicitly out of scope

- Real-time co-browsing operator console (mocked at a real seam — §12.4)
- Desktop / native surface adapter (port defined, adapter not implemented — §14.1)
- Queues, workers, clusters, multi-tenant storage plumbing (brief explicitly does not reward this)
- Auth/SSO, RBAC, user management
- Any real bank system, real credentials, or real PII

### 2.5 Constraints

- One genuine LLM-driven discovery run against a live surface is **mandatory**, with evidence in `/evidence/`.
- Secrets never in repo. `.env` + `.env.example`.
- CI must run green **without** an API key (discovery tests use recorded LLM cassettes).
- Self-imposed time box: ~24 engineering hours. Judgment, not endurance.

---

## 3. Personas and user stories

| # | Persona | Story | Satisfied by |
|---|---|---|---|
| P1 | **Automation Engineer** (builds capabilities) | "I give a goal in English and get back a reviewable capability I can diff in a PR." | §7.1 discovery, §8 artifact |
| P2 | **Calling AI Agent** (production consumer) | "I call `member.read_savings_balance(member_id)` and get typed outputs or a typed outcome — never a stack trace." | §10 replay contract, §19 capability catalog |
| P3 | **Human Operator** (bank staff) | "When the robot gets stuck, I get a request with context, I finish the step in the same session, and I hand it back." | §12 escalation |
| P4 | **Compliance / Risk Reviewer** | "I can read what a capability is permitted to do, and prove no PII was persisted." | §11 guardrails, §13 evidence |
| P5 | **SRE / On-call** | "A failed replay tells me which step, what was expected, what was observed, with a screenshot." | §13 observability |

---

## 4. Goals, non-goals, success metrics

### 4.1 Goals

- **G1** — Complete a non-trivial multi-step goal via LLM-driven UI interaction against a live surface.
- **G2** — Emit a typed, versioned, human-reviewable capability artifact decoupled from the model transcript.
- **G3** — Replay that artifact with zero LLM decisions, verify a checkpoint, return typed outputs.
- **G4** — Classify every runtime condition into business outcome / recoverable / hard failure.
- **G5** — Detect stuck, escalate with context, transfer control of the *same* live session, resume.
- **G6** — Enforce allowlist + action-risk policy; persist no secrets or raw PII.
- **G7** — Produce evidence sufficient to debug or audit any run.

### 4.2 Non-goals

Feature breadth, framework name-dropping, scaling infrastructure, polished UI, high test coverage percentage for its own sake.

### 4.3 Success metrics (measured, reported in `/evidence/`)

| Metric | Target |
|---|---|
| Discovery success on the primary goal | ≥1 genuine run, evidenced |
| Replay determinism (10 consecutive runs, happy path) | 10/10 identical step path and outputs |
| Locator rung-1 hit rate on replay | ≥90% (rung>1 logged as drift signal) |
| Fault scenarios correctly classified | 8/8 in the fault matrix (§16.4) |
| Replay p50 latency vs discovery latency | ≤10% (demonstrates the economic point) |
| Secrets/PII in artifacts or logs | 0, asserted by an automated scanner test |

---

## 5. Requirements traceability matrix

| Brief req | Requirement | Component | Evidence | Test IDs |
|---|---|---|---|---|
| 3.1 | Goal + target input | `cli`, `Goal` model | `evidence/discovery/*/run.jsonl` | T-DIS-01..04 |
| 3.1 | LLM observe→decide→act loop | `discovery/agent.py` | same | T-DIS-01 |
| 3.1 | Stopping conditions | `discovery/limits.py` | `run.jsonl` `stop_reason` | T-DIS-05..07 |
| 3.1 | Real UI interaction, no-clean-DOM bias | `surface/web_aria.py` | AX snapshots in evidence | T-SUR-01..06 |
| 3.2 | Typed serializable artifact | `schema/capability.py` (Pydantic) | `evidence/artifacts/*.yaml` | T-SCH-01..12 |
| 3.2 | Locator identification + rationale | `Target.strategies` + `rationale` | artifact | T-LOC-01..08 |
| 3.2 | Typed inputs / outputs | `InputParam`, `OutputField` | artifact | T-SCH-05..08 |
| 3.2 | Checkpoint / success condition | `Checkpoint` | artifact | T-CHK-01..04 |
| 3.2 | Versioned + reviewable | `schema_version`, `capability.version`, YAML | `git diff` of artifact | T-SCH-09..10 |
| 3.3 | LLM-free replay | `replay/executor.py` (no llm import) | import-boundary test | T-REP-01, T-ARCH-01 |
| 3.3 | Stable targeting + checkpoint verify | `replay/resolver.py` | `replay/*/run.jsonl` | T-LOC-01..08 |
| 3.3 | 3-way error classification | `errors/taxonomy.py`, step `expectations` | fault-matrix evidence | T-ERR-01..12 |
| 3.3 | Structured result | `ReplayResult` | `result.json` | T-REP-02..06 |
| 3.4 | Allowlist enforcement | `policy/allowlist.py` | blocked-attempt log | T-POL-01..06 |
| 3.4 | Risky-action handling | `policy/risk.py` | confirmation record | T-POL-07..10 |
| 3.4 | No secrets / raw PII persisted | `policy/redaction.py` | scanner test output | T-SEC-01..05 |
| 3.5 | Structured log + rich failure signal | `obs/logger.py`, `obs/evidence.py` | evidence bundle | T-OBS-01..05 |
| 3.6 | Detect stuck + route request | `escalation/detector.py`, `InterventionRequest` | `intervention.json` | T-ESC-01..04 |
| 3.6 | Human drives same session, hands back | `session/lease.py`, mock operator console | `handoff.jsonl` | T-ESC-05..10 |
| 3.7 | Surface abstraction story | `REPORT.md` §4 | — | design review |
| 3.7 | Multi-tenant reuse story | `REPORT.md` §4, `overlay.py` (loader only) | overlay demo | T-MT-01..03 |

---

## 6. Technology decisions (ADR summary)

### ADR-001 — Language & runtime: **Python 3.12**

*Alternatives:* TypeScript/Node, Go.
*Rationale:* Pydantic v2 gives schema-as-code with JSON Schema export for free — the artifact schema is the focal point of evaluation, and this makes it typed, validated, and self-documenting in one place. Playwright's Python API is first-class. The calling side (AI agents) is Python-heavy.
*Trade-off:* Node would let the agent share a runtime with browser code; not worth losing Pydantic.

### ADR-002 — Computer-use technology: **Playwright (Chromium, persistent context) as the driver; accessibility tree as the primary perception channel**

*Alternatives:* pure screenshot+coordinates (Anthropic computer-use tool), Selenium, OS automation (pywinauto/UIA).
*Rationale:* The brief wants an approach that survives with no clean DOM. Playwright is the *transport*; the *perception model* is deliberately AX-tree + screenshot, so the recorded artifact never depends on markup quality. Playwright also gives us frame handling (essential for framesets), CDP access (essential for live-session handoff), and video/trace (evidence).
*Trade-off:* Not literally OS-level, so a native desktop app needs a new adapter — but the `Surface` port is defined so that adapter is additive (§14.1).

### ADR-003 — LLM: **Anthropic Claude Sonnet, tool-use (structured function calling), not free-text parsing**

*Rationale:* Tool schemas force the model to emit exactly the action vocabulary the replay engine understands. This is what makes discovery → artifact a translation rather than an inference. Temperature 0. Every request/response persisted as a cassette for CI replay.
*Trade-off:* Vendor coupling; mitigated by a one-file `llm/client.py` port.

### ADR-004 — Target application: **local `legacybank` app (FastAPI + Jinja, deliberately hostile markup) with two tenant variants and a fault-injection control plane**

*Rationale:* This is the single highest-leverage decision. We need: (a) framesets, nested tables, no test IDs, inline `onclick` navigation, 1990s server-rendered forms; (b) the ability to *cause* validation errors, record-not-found, permission denial, surprise interstitials, session expiry, transient slowness, and 500s on demand; (c) a second variant of the same "vendor product" for the cross-tenant demo; (d) hermetic CI with no ToS or rate-limit exposure. No public demo site provides (b), (c), or (d).
*Trade-off:* We build the target, so we could accidentally make it easy. Mitigation: the app is written to a hostility checklist (§7.4) **before** the agent is written, and never edited to make a failing agent pass.

### ADR-005 — Artifact storage: **YAML files on disk, git-tracked, JSON Schema published**

*Rationale:* Reviewable is a stated requirement — a capability change must show up as a readable PR diff. YAML for humans, JSON Schema for machines/validation, filesystem because a database is scaling infrastructure the brief tells us not to build.
*Trade-off:* No query/catalog at scale; noted as next step.

### ADR-006 — Architecture: **single process, library-first, three CLI entry points; no services**

*Rationale:* Simpler is fine if justified. The only genuine cross-process need is the human handoff, and that is solved with a long-lived browser process + a lease store, not a service mesh. Every module is import-clean so it can be lifted into a worker later.
*Trade-off:* No concurrency story; explicitly a next step.

### ADR-007 — Full stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.12, `uv` for deps |
| Schema/validation | Pydantic v2, JSON Schema export |
| Browser driver | Playwright (Chromium, headed for handoff, headless for CI) |
| LLM | Anthropic Python SDK, tool-use, temperature 0 |
| CLI | Typer + Rich |
| Target app | FastAPI + Jinja2, server-rendered, session cookies |
| Operator console (mock) | FastAPI + one HTML page (screenshot poll + click/type forward) |
| Logging | `structlog` → JSONL |
| Serialization | `ruamel.yaml` (round-trip, preserves comments) |
| Testing | pytest, pytest-asyncio, pytest-playwright, `syrupy` snapshots, `respx`-style LLM cassettes |
| Lint/type | ruff, mypy strict on `schema/`, `replay/`, `policy/` |
| CI | GitHub Actions: lint → type → unit → integration (local app) → contract snapshots |

---

## 7. Architecture

### 7.1 Component view

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLI  (typer)                                │
│   handspan discover   |   handspan replay   |   handspan operator        │
└───────┬──────────────────────────┬──────────────────────┬────────────────┘
        │                          │                      │
┌───────▼─────────┐      ┌─────────▼──────────┐   ┌───────▼─────────┐
│  DISCOVERY      │      │  REPLAY ENGINE     │   │ OPERATOR CONSOLE│
│  ENGINE         │      │  (no LLM imports)  │   │  (mock, real    │
│                 │      │                    │   │   seam)         │
│ observe→decide  │      │ step loop          │   │ screenshot poll │
│ →act loop       │      │ locator resolve    │   │ click / type    │
│ trace → compile │      │ checkpoint verify  │   │ release control │
└───┬────────┬────┘      └───┬────────┬───────┘   └───────┬─────────┘
    │        │               │        │                   │
    │   ┌────▼───────────────▼────┐   │                   │
    │   │  ARTIFACT COMPILER /    │   │                   │
    │   │  LOADER + OVERLAY       │   │                   │
    │   │  (Pydantic, YAML)       │   │                   │
    │   └─────────────────────────┘   │                   │
    │                                 │                   │
┌───▼─────────────────────────────────▼───────────────────▼─────────────┐
│                        SHARED KERNEL                                  │
│  policy/ (allowlist, risk, redaction)   session/ (lease, state)       │
│  errors/ (taxonomy, classifier)         obs/ (logger, evidence)       │
│  escalation/ (detector, request bus)                                  │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────────────┐
│                     SURFACE PORT  (abstract)                          │
│   observe() -> Observation{ax_tree, screenshot, url, frames, text}    │
│   act(Action) -> ActionResult      resolve(Target) -> Handle          │
│   session_info()  pause()  resume()                                   │
├──────────────────────┬────────────────────────────────────────────────┤
│ WebAriaSurface       │ (future) LegacyFrameSurface  DesktopUiaSurface │
│ (Playwright+AX+CDP)  │           — port defined, not built —          │
└──────────────────────┴────────────────────────────────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │  legacybank app     │
                     │  tenant A / B       │
                     │  fault injection    │
                     └─────────────────────┘
```

### 7.2 The two load-bearing seams

**Seam 1 — Surface port.** Everything above the port speaks in `Observation` / `Action` / `Target`. Nothing above the port knows what a CSS selector is. This is the seam that makes desktop support additive rather than a rewrite.

**Seam 2 — Artifact.** Discovery's only output is an artifact. Replay's only input is an artifact + params. There is no shared runtime state, no pickled model context, no transcript dependency. Enforced by an architecture test: `replay/` must not import `discovery/` or `llm/`.

### 7.3 Sequence — discovery run

```
CLI            Agent            Policy         Surface        LLM         Compiler
 │ goal,target   │                │              │              │             │
 ├──────────────▶│                │              │              │             │
 │               ├─ check target ▶│              │              │             │
 │               │◀ allowed ──────┤              │              │             │
 │               ├─ observe ──────────────────▶  │              │             │
 │               │◀ ax_tree+shot+url ─────────── │              │             │
 │               ├─ prompt(goal, obs, history, tools) ─────────▶│             │
 │               │◀ tool_call{action, target_hint, rationale} ──┤             │
 │               ├─ classify risk + allowlist ──▶│              │             │
 │               │   (block / confirm / allow)   │              │             │
 │               ├─ synthesise locator ladder from AX node ──▶  │             │
 │               ├─ act ─────────────────────────▶              │             │
 │               │◀ ActionResult + post-observation ──────────  │             │
 │               ├─ append TraceStep (redacted)                 │             │
 │               │   ... loop until goal_reached | stop_reason   │             │
 │               ├─ if stuck ──▶ escalation.raise()             │             │
 │               ├─ trace ────────────────────────────────────────────────▶   │
 │               │                                              │  compile:   │
 │               │                                              │  prune,     │
 │               │                                              │  parameterise│
 │               │                                              │  ladder,    │
 │               │                                              │  checkpoints│
 │◀ artifact.yaml + evidence bundle ──────────────────────────────────────────┤
```

**Trace vs artifact — why compilation is a separate step.** The raw trace contains dead ends, retries, model rationales, and concrete values. The compiler produces the artifact by: (1) pruning steps that were reverted or had no state effect; (2) replacing concrete values that came from the goal with `from_input` references (member ID `12345` → `{{ member_id }}`) and declaring the input's type/pattern; (3) promoting the AX node that was acted on into a full locator ladder; (4) attaching a checkpoint to every state-changing step, derived from the post-action observation diff; (5) attaching the default expectation table for the app profile plus any exceptional states actually encountered; (6) stripping all rationale text through the redactor. This is the step that makes the artifact "decoupled from the raw model transcript" rather than a rebranded log.

### 7.4 Target app hostility checklist (written first, frozen)

- `<frameset>` with `nav` / `content` frames — targets must carry frame identity
- Layout via nested `<table>`, no `<main>`/`<section>`, no ARIA landmarks beyond what the browser infers
- Zero `data-testid`; ids like `ctl00_mbrSrch_txt1`, regenerated per deploy in tenant B
- Labels adjacent in sibling `<td>`, not `<label for>` — forces label-proximity locator rung
- Navigation via `<a href="javascript:__doPostBack(...)">` and full page reloads
- Server-rendered validation errors in a red `<span>` inside the form table
- Session cookie with 60s idle expiry (configurable) → real session-timeout scenario
- Randomised 200–1200ms server latency; `?fault=` control plane for deterministic faults
- Tenant B: same product, different brand CSS, different field order, one extra mandatory field, renamed button ("Find" → "Search"), different id prefix

**Primary flow (the goal):** login → member search → member detail → open sub-account form (multi-field) → confirmation screen. Covers search→detail→action *and* a multi-field form with confirmation.

**Primary discovery goal string:** *"Look up member 100234 and read their current savings balance."*
**Secondary goal (risky-action path):** *"Open a new savings sub-account for member 100234 and reach the confirmation screen."*

---

## 8. Artifact schema (the focal point)

### 8.1 Design principles

1. **Contract before steps.** A caller must understand inputs/outputs/outcomes without reading the step list.
2. **Values never live in the artifact.** Steps reference inputs; inputs carry type + sensitivity. This makes "no PII in artifacts" structural, not procedural.
3. **A target is a ranked set of hypotheses, not a selector.**
4. **Every step declares what it expects next.** Checkpoints and expectation tables are part of the recording, so replay's error handling is data, not code.
5. **Identity is the product, not the tenant.** `product` + `product_version` + `tenant_scope`.
6. **Two version axes.** `schema_version` (semver, engine compatibility) and `capability.version` (integer, content revision).

### 8.2 Top-level schema

```yaml
schema_version: "1.0.0"

capability:
  id: cap.member.read_savings_balance      # stable, namespaced, tenant-free
  version: 3                                # bumped on any semantic change
  name: Read member savings balance
  description: >
    Looks up a member by member ID in the servicing console and returns the
    current savings balance shown on the member detail screen.
  status: approved                          # draft | approved | deprecated
  labels: [member, read-only, balance]

target:
  surface:
    kind: web                               # web | legacy_web | desktop
    adapter: web_aria/1                     # which Surface implementation
  app:
    product: CoreVantage Servicing          # the vendor product
    product_version: "9.4"
    tenant_scope: base                      # base | tenant:<id>
    entry: { url_template: "{base_url}/servicing/home", requires_session: true }
  allowlist_ref: policies/corevantage.yaml

inputs:
  - name: member_id
    type: string
    required: true
    pattern: "^[0-9]{6}$"
    sensitivity: identifier                 # public | identifier | pii | secret
    description: Institution member number
    example: "100234"

outputs:
  - name: savings_balance
    type: money
    required: true
    source: { step: s6, extractor: ax_text, transform: parse_money }
    sensitivity: pii
  - name: account_status
    type: enum
    values: [active, dormant, frozen]
    required: false
    source: { step: s6, extractor: ax_text, transform: lower_trim }
    sensitivity: identifier

outcomes:                                   # declared business outcomes (not errors)
  - code: MEMBER_NOT_FOUND
    description: No member matches the supplied ID.
    detected_at: s4
  - code: PERMISSION_DENIED
    description: Session lacks entitlement to view this member.
    detected_at: s5

policy:
  risk_class: safe                           # safe | risky
  side_effects: none                         # none | reversible | irreversible
  requires_approval_for_unattended: false
  max_runtime_ms: 45000

steps: [ ... ]                               # §8.3

reliability:
  replays: 41
  successes: 40
  last_verified_at: "2026-08-12T09:14:22Z"
  stability_score: 0.976
  locator_degradations: [{ step: s3, rung_used: 2, count: 3 }]

provenance:
  discovered_by: claude-sonnet-4-6
  discovery_run_id: dsc_01J9Z...
  discovered_at: "2026-08-10T11:02:07Z"
  compiler_version: "1.0.0"
  evidence_ref: evidence/discovery/dsc_01J9Z/
  human_edits: [{ at: "...", by: "raj", note: "tightened s4 checkpoint" }]
```

### 8.3 Step schema

```yaml
steps:
  - id: s3
    intent: Enter the member ID into the search field
    action: type                            # see §8.5 action vocabulary
    target:
      frame: content                        # frameset-aware
      rationale: >
        Accessible name "Member ID" is rendered from the server-side label and is
        identical across tenants A and B; the id attribute is ASP.NET-generated
        and changes per deploy, so it is the last rung.
      strategies:                           # ordered ladder, first unique match wins
        - { kind: ax_role_name, role: textbox, name: "Member ID", match: exact }
        - { kind: ax_label_proximity, label: "Member ID", direction: right, max_distance: 2 }
        - { kind: table_cell_neighbour, label_text: "Member ID", cell_offset: [0, 1] }
        - { kind: css, value: "input[id$='txtMemberId']" }
        - { kind: visual_anchor, anchor_text: "Member ID", offset: [140, 0], requires: screenshot }
      match_policy: require_unique          # require_unique | first | nth
      recorded_rung: 1
    value: { from_input: member_id }         # never a literal for typed input
    waits:
      before: { kind: ax_stable, timeout_ms: 4000 }
      after:  { kind: none }
    checkpoint:
      kind: ax_value_equals
      role: textbox
      name: "Member ID"
      expected: { from_input: member_id }
    expectations: []                         # inherits app-profile defaults
    risk: safe
    timeout_ms: 8000
    retry: { attempts: 2, backoff_ms: 400, on: [stale_handle, transient_load] }

  - id: s4
    intent: Submit the member search
    action: click
    target:
      frame: content
      strategies:
        - { kind: ax_role_name, role: button, name: "Find", match: fuzzy, aliases: ["Search", "Go"] }
        - { kind: table_cell_neighbour, label_text: "Member ID", cell_offset: [1, 0] }
        - { kind: css, value: "input[type=submit][value*='Find' i]" }
      match_policy: require_unique
    waits:
      after: { kind: navigation_or_ax_change, timeout_ms: 12000 }
    checkpoint:
      kind: any_of
      conditions:
        - { kind: ax_present, role: heading, name_matches: "^Member .* Detail$" }
        - { kind: text_present, value: "No records found" }
    expectations:                            # step-local branch table
      - when: { kind: text_present, value: "No records found" }
        classify: business_outcome
        outcome: MEMBER_NOT_FOUND
        halt: true
      - when: { kind: text_matches, value: "not authori[sz]ed|entitlement" }
        classify: business_outcome
        outcome: PERMISSION_DENIED
        halt: true
      - when: { kind: ax_present, role: alertdialog, name_matches: "System Notice" }
        classify: recoverable
        recovery: { action: dismiss_dialog, accept_names: ["OK", "Close"] }
        max_attempts: 2
      - when: { kind: text_present, value: "Your session has expired" }
        classify: hard_failure
        code: SESSION_EXPIRED
    risk: safe
    timeout_ms: 15000

  - id: s6
    intent: Read the savings balance from the member detail panel
    action: extract
    target:
      frame: content
      strategies:
        - { kind: ax_label_proximity, label: "Savings Balance", direction: right, max_distance: 2 }
        - { kind: table_cell_neighbour, label_text: "Savings Balance", cell_offset: [0, 1] }
        - { kind: regex_in_region, region_anchor: "Savings", pattern: "\\$[0-9,]+\\.[0-9]{2}" }
    extract_to: savings_balance
    checkpoint: { kind: matches, pattern: "^\\$[0-9,]+\\.[0-9]{2}$" }
    risk: safe
```

### 8.4 Locator strategy ladder — rationale

| Rung | Kind | Survives | Fails when |
|---|---|---|---|
| 1 | `ax_role_name` | markup rewrites, id churn, CSS rebrands, tenant restyling; works on desktop via UIA | label text is renamed or localised |
| 2 | `ax_label_proximity` | missing `<label for>`, table layouts | visual/DOM order changes |
| 3 | `table_cell_neighbour` | non-semantic legacy tables specifically | table restructure |
| 4 | `css` / `xpath` | nothing interesting; kept as a fast path and a tie-breaker | any markup change |
| 5 | `visual_anchor` (OCR/template) | total DOM absence — the desktop / Citrix case | zoom, theme, resolution change |

Two properties make this more than a fallback chain:

- **Drift sensor.** `recorded_rung` is stored; replay logs `rung_used`. Rung inflation across runs is the leading indicator that a tenant's app changed, feeding §14.2 drift detection *without* any diffing infrastructure.
- **Ambiguity is a failure, not a coin flip.** `match_policy: require_unique` means a locator matching 3 elements raises `AMBIGUOUS_TARGET` rather than silently picking the first. Silent wrong-element selection is the worst failure mode in a banking context.

### 8.5 Action vocabulary (closed set — this *is* the LLM's tool schema)

| Action | Params | Risk default |
|---|---|---|
| `navigate` | `url_template` | safe (allowlist-checked) |
| `click` | `target` | safe unless target risk-flagged |
| `type` | `target`, `value` | safe |
| `select` | `target`, `option` | safe |
| `press_key` | `key` | safe |
| `wait_for` | `condition`, `timeout_ms` | safe |
| `extract` | `target`, `extract_to` | safe |
| `assert` | `condition` | safe |
| `submit_form` | `target` | **risky** if `side_effects != none` |
| `confirm_dialog` | `accept_names` | risky |
| `escalate` | `reason`, `context` | safe |
| `finish` | `status`, `outputs` | safe |

The same closed set is (a) the LLM tool definitions, (b) the artifact step vocabulary, (c) the replay executor's dispatch table. One vocabulary, three consumers — this is what prevents discovery from producing steps replay cannot execute.

### 8.6 Versioning & review

- `schema_version` bumps major on breaking field changes; the loader refuses artifacts with an unsupported major and says so.
- `capability.version` increments on any change to inputs, outputs, outcomes, or steps. Diffing two YAML files in a PR is the review mechanism.
- `status: draft → approved` gates unattended replay (`--unattended` refuses `draft`).
- `reliability` is engine-written telemetry, excluded from semantic diffs by a git attribute so it does not create review noise.

---

## 9. Discovery engine design

### 9.1 Loop

```
state = Observation(surface.observe())
for step_no in 1..MAX_STEPS:
    if budget_exceeded(steps|wallclock|tokens): stop(BUDGET)
    decision = llm.decide(goal, state, history, tool_schema)   # temperature 0
    verdict  = policy.evaluate(decision)                        # allow|confirm|block
    if verdict.blocked: history.append(refusal); continue        # model must re-plan
    if decision.action == finish: validate_outputs(); break
    if decision.action == escalate: escalation.raise(...); break
    result = surface.act(decision.action)
    state  = Observation(surface.observe())
    trace.append(TraceStep(decision, result, state.digest, redacted=True))
    if no_state_change_for(3): stop(DEAD_END) -> escalate
```

### 9.2 What the model sees

- Goal, plus the typed inputs already extracted from the goal
- Compacted AX tree of the focused frame: role, accessible name, value, enabled/focused, plus a stable node ref — **truncated by relevance, not by depth** (interactive nodes and nodes near the last action are kept)
- Screenshot (downscaled) for layout-dependent decisions
- Current URL, frame inventory, last action + its result
- Step budget remaining, and the list of allowed actions
- **Never** raw HTML. Deliberate: if the model cannot see markup, it cannot produce markup-coupled plans.

### 9.3 Stopping conditions

`GOAL_REACHED` · `MAX_STEPS` (default 25) · `WALLCLOCK` (default 180s) · `TOKEN_BUDGET` · `DEAD_END` (3 consecutive no-op observations) · `POLICY_BLOCKED` (same block twice) · `ESCALATED` · `SURFACE_ERROR`.

Every non-`GOAL_REACHED` stop writes an evidence bundle and, if it represents a recoverable-by-human situation, an intervention request.

---

## 10. Replay engine and result contract

### 10.1 Determinism strategy

Determinism is not "hope the same thing happens." It is five explicit mechanisms:

1. **No model in the decision path.** Architecturally enforced by an import-boundary test.
2. **Closed action vocabulary + resolved targets.** Nothing is inferred at runtime; the ladder is data.
3. **Explicit waits, no sleeps.** Every step waits on a *condition* (`ax_stable`, `navigation_or_ax_change`, `ax_present`, `text_present`) with a timeout. `sleep()` is banned by a lint rule.
4. **Checkpoint after every state-changing step.** A click is not "done" because it dispatched; it is done because the expected state arrived.
5. **Idempotent input binding.** Same params → same typed values → same keystrokes. Params are validated against `inputs` before step 1, so bad input fails fast as `INVALID_INPUT`, never mid-flow.

### 10.2 Error taxonomy

**Class A — Business outcomes** (the flow worked; the answer is "no"). Declared per capability in `outcomes`. Terminal status `business_outcome`. HTTP analogue: 200 with a typed result.

| Code | Trigger |
|---|---|
| `MEMBER_NOT_FOUND` | "No records found" on search result |
| `PERMISSION_DENIED` | entitlement text or 403 screen |
| `VALIDATION_REJECTED` | server-rendered field error on submit |
| `DUPLICATE_RECORD` | "sub-account already exists" |
| `LIMIT_EXCEEDED` | business rule cap hit |

**Class B — Recoverable conditions** (retry/dismiss/wait, bounded, then reclassify to Class C).

| Code | Recovery | Bound |
|---|---|---|
| `TRANSIENT_LOAD` | re-wait with backoff | 2 |
| `KNOWN_INTERSTITIAL` | dismiss dialog by allowed name | 2 |
| `STALE_HANDLE` | re-resolve ladder from rung 1 | 2 |
| `NAV_RACE` | re-observe, re-checkpoint | 1 |
| `RATE_LIMITED` | backoff | 2 |

**Class C — Hard failures** (stop, escalate if configured, emit debuggable evidence).

| Code | Meaning |
|---|---|
| `SESSION_EXPIRED` | login screen / expiry banner mid-flow |
| `LOCATOR_EXHAUSTED` | all ladder rungs failed |
| `AMBIGUOUS_TARGET` | >1 unique match under `require_unique` |
| `CHECKPOINT_MISMATCH` | expected state never arrived |
| `APP_ERROR` | 5xx / error page |
| `POLICY_BLOCKED` | step outside allowlist or risky without approval |
| `TIMEOUT_EXCEEDED` | step or capability budget |
| `INVALID_INPUT` | params failed schema before execution |
| `SCHEMA_INCOMPATIBLE` | artifact major version unsupported |
| `UNEXPECTED_STATE` | nothing in the expectation table matched — the honest default |

**Classification order per step:** checkpoint satisfied? → declared `expectations` in order → app-profile default expectations → `UNEXPECTED_STATE`. Never guess a class; unknown is its own hard failure with full evidence.

### 10.3 Replay result contract

```json
{
  "run_id": "rpl_01J9ZQ8F",
  "capability": { "id": "cap.member.read_savings_balance", "version": 3,
                  "schema_version": "1.0.0" },
  "status": "success",
  "started_at": "2026-08-12T09:14:19.220Z",
  "duration_ms": 4180,
  "inputs_digest": "sha256:9f2c…",
  "outputs": { "savings_balance": "$4,215.60", "account_status": "active" },
  "outcome": null,
  "failure": null,
  "steps": [
    { "id": "s3", "action": "type", "status": "ok", "duration_ms": 210,
      "rung_used": 1, "checkpoint": "passed" },
    { "id": "s4", "action": "click", "status": "ok", "duration_ms": 1890,
      "rung_used": 2, "checkpoint": "passed",
      "recoveries": [{ "code": "KNOWN_INTERSTITIAL", "attempts": 1 }] }
  ],
  "degradations": [{ "step": "s4", "recorded_rung": 1, "rung_used": 2,
                     "signal": "possible_ui_drift" }],
  "control": { "holder": "automation", "handoffs": [] },
  "evidence_ref": "evidence/replay/rpl_01J9ZQ8F/"
}
```

Business-outcome variant:

```json
{ "status": "business_outcome",
  "outcome": { "code": "MEMBER_NOT_FOUND", "detected_at_step": "s4",
               "message": "No member matches the supplied ID.",
               "caller_action": "surface_to_user" },
  "outputs": {}, "failure": null }
```

Hard-failure variant:

```json
{ "status": "failed",
  "failure": { "code": "CHECKPOINT_MISMATCH", "step": "s5",
               "expected": "heading matching '^Sub-account Confirmation$'",
               "observed": "heading 'Member 100234 Detail'; alert 'Product code required'",
               "rung_used": 1, "recoveries_attempted": ["TRANSIENT_LOAD x1"],
               "evidence": { "screenshot": "…/s5-fail.png",
                             "ax_snapshot": "…/s5-ax.json",
                             "trace": "…/trace.zip" },
               "remediation_hint": "Step s5 may need an added required field; re-record or add tenant overlay." },
  "escalation": { "raised": true, "request_id": "int_01J9ZR2" } }
```

**Caller-facing guarantee:** `status` alone tells an agent what to do — `success` use outputs, `business_outcome` relay to the user, `failed` retry or alert, `escalated` wait on the intervention request.

---

## 11. Safety and policy guardrails

### 11.1 Allowlist (declarative, per app profile)

```yaml
# policies/corevantage.yaml
version: 1
domains: ["localhost:8081", "*.corevantage-sandbox.internal"]
routes:
  allow: ["/servicing/**", "/member/**", "/subaccount/new", "/subaccount/confirm"]
  deny:  ["/admin/**", "/export/**", "/wire/**", "/user-management/**"]
actions:
  allow: [navigate, click, type, select, press_key, wait_for, extract, assert, submit_form]
  deny:  [file_download, file_upload, execute_script, open_new_window]
risky_actions:
  submit_form: { when_side_effects: [reversible, irreversible] }
  confirm_dialog: always
data:
  forbid_typing_into: [ "role=textbox name~=(SSN|Social Security|Tax ID)" ]
  max_extractions_per_run: 20
limits: { max_steps: 25, max_runtime_ms: 180000 }
```

Enforcement is a **pre-flight gate on every action in both engines** — discovery and replay share one `policy.evaluate()`. A blocked action in discovery is fed back to the model as a refusal (it must re-plan); a blocked action in replay is `POLICY_BLOCKED`, a hard failure. Navigation is checked *before* it happens, and the resulting URL is checked again after, so a server-side redirect out of the allowlist is caught too.

### 11.2 Risky vs safe actions

Classification: an action is **risky** if it causes a non-reversible or externally-visible side effect (money movement, record creation, permission change, notification send) or if it accepts a confirmation dialog.

Chosen handling: **block-by-default in unattended replay; require explicit confirmation otherwise.**

| Mode | Safe action | Risky action |
|---|---|---|
| Discovery (interactive) | execute | pause → CLI confirmation prompt → record the confirmation in the trace |
| Replay, `--attended` | execute | raise intervention request, human approves in operator console |
| Replay, `--unattended` | execute | `POLICY_BLOCKED` unless `capability.policy.requires_approval_for_unattended` was satisfied by an approver recorded in the artifact |

*Justification:* in a regulated environment the cost asymmetry is extreme — a blocked legitimate action costs a human 30 seconds; an unblocked wrong one is a compliance incident. Fail closed, and make the approval path cheap enough that failing closed is tolerable.

### 11.3 Sensitive data handling

Three rules, enforced in code rather than by convention:

1. **Values never enter artifacts.** Steps carry `from_input` references. The compiler raises if a step contains a literal that matches any input value or any sensitivity pattern.
2. **Redaction at capture, not at write.** `obs/logger.py` pipes every record through `policy/redaction.py` before it reaches a buffer, so a crash cannot flush unredacted data. Patterns: SSN, card PAN (Luhn-checked), account numbers, bearer tokens, `Authorization` headers, cookies, email, phone. Replacement: `«redacted:pan»` with a stable salted hash suffix so correlation survives redaction.
3. **Screenshots are treated as PII.** Failure screenshots get masked regions derived from AX nodes whose accessible name matches sensitive patterns, and the evidence directory is written with `0700` and a `README` stating retention (7 days, local only).

Outputs are the deliberate exception: a capability whose whole purpose is returning a balance must return it. Outputs are declared with `sensitivity`, returned to the caller in memory, and **written to the result file only when `--persist-outputs` is passed** (off in CI, off by default).

An automated test (`T-SEC-04`) greps every artifact and log produced by the full test suite for the fixture PII corpus and fails the build on any hit.

---

## 12. Escalation and human handoff

### 12.1 Control model

One session, one holder, explicit lease:

```
                 ┌──────────────────┐
     start ─────▶│ AUTOMATION_HELD  │◀─────────────┐
                 └────────┬─────────┘              │
              stuck /     │                        │ resume_granted
              risky /     ▼                        │ (+ state re-verified)
              hard fail  ┌──────────────────┐      │
                         │ PAUSE_REQUESTED  │      │
                         └────────┬─────────┘      │
                    automation     │               │
                    quiesced       ▼               │
                         ┌──────────────────┐      │
                         │  HUMAN_HELD      │──────┘
                         └────────┬─────────┘
                                  │ abandon / timeout
                                  ▼
                         ┌──────────────────┐
                         │   TERMINATED     │
                         └──────────────────┘
```

The lease lives in `session/lease.py` backed by a JSON file + file lock (single-process today, swappable for Redis). **The executor checks the lease before every action.** If it does not hold the lease, it does not act — this is the mechanism that makes "the human is driving" safe rather than a race.

### 12.2 Detecting stuck

| Trigger | Where | Class |
|---|---|---|
| 3 consecutive observations with no state change | discovery | dead end |
| Same policy block twice | both | blocked |
| Hard failure with `escalate_on: true` | replay | blocked |
| Risky action in attended mode | replay | approval needed |
| `LOCATOR_EXHAUSTED` / `AMBIGUOUS_TARGET` | replay | blocked |
| Model emits `escalate` tool call | discovery | self-reported |
| `SESSION_EXPIRED` | replay | needs human credentials (we never type them) |

### 12.3 Intervention request

```json
{
  "request_id": "int_01J9ZR2",
  "created_at": "2026-08-12T09:20:41Z",
  "kind": "blocked",
  "priority": "normal",
  "run": { "run_id": "rpl_01J9ZQ8F", "mode": "replay",
           "capability": "cap.member.open_subaccount@4",
           "goal": "Open a new savings sub-account and reach confirmation" },
  "stopped_at": { "step": "s7", "intent": "Submit the sub-account form",
                  "attempt": 2 },
  "why": { "code": "VALIDATION_REJECTED_UNEXPECTED",
           "expected": "heading '^Sub-account Confirmation$'",
           "observed": "alert 'Product code required'" },
  "state": { "url": "https://localhost:8081/subaccount/new",
             "frame": "content",
             "screenshot": "evidence/replay/rpl_01J9ZQ8F/s7-fail.png",
             "ax_snapshot": "evidence/replay/rpl_01J9ZQ8F/s7-ax.json" },
  "inputs_redacted": { "member_id": "«redacted:identifier:8a1f»" },
  "session": { "session_id": "sess_01J9ZP", "lease_state": "PAUSE_REQUESTED",
               "takeover_url": "http://localhost:8090/operator/sess_01J9ZP" },
  "allowed_human_actions": ["click", "type", "select", "navigate_within_allowlist"],
  "resume_contract": { "resume_at_step": "s7",
                       "required_state": { "kind": "ax_present", "role": "heading",
                                           "name_matches": "^Sub-account" },
                       "on_state_mismatch": "abort_with_failure" }
}
```

`resume_contract` is the important field: the human is not trusted to have left the app in an arbitrary state. On resume the executor **re-verifies `required_state`** before continuing, and aborts cleanly if the world does not match.

### 12.4 Taking control of the *same* live session

This is the part that must be real, not a TODO. Mechanism:

- The browser is a **persistent Playwright context in a long-lived process**, owned by the run, headed. It is not torn down on pause.
- On `PAUSE_REQUESTED`, the executor finishes the in-flight action, snapshots evidence, sets the lease to `HUMAN_HELD`, and enters a wait loop. No further actions are dispatched.
- The operator console (mocked UI, real mechanism) attaches to **that same context** and exposes it two ways:
  - **Bare mode (default, always works):** the console prints the takeover URL and the human interacts directly with the already-open headed browser window. An injected `MutationObserver` + event-capture script records human clicks/inputs (selectors + redacted values + timestamps) into `handoff.jsonl`.
  - **Console mode:** a single-page FastAPI surface polling `page.screenshot()` at 2fps and forwarding click/type events to the same page via CDP. Deliberately minimal — the brief says the console is out of scope; the *seam* is what matters.
- The human clicks **Hand back** (or `POST /operator/{session}/release`). Lease → `RESUME_REQUESTED`.
- Executor wakes, re-observes, verifies `resume_contract.required_state`, appends a `human_intervention` pseudo-step to the run record (what the human did, redacted), and resumes at `resume_at_step`. If verification fails → `status: failed`, code `RESUME_STATE_MISMATCH`, evidence attached.
- Timeout (default 15 min) → `TERMINATED`, `status: escalated` with `abandoned: true`.

The human's actions are **recorded but not promoted into the artifact automatically.** They are emitted as a suggested step patch in the evidence bundle for a human to review and merge — auto-learning from an unreviewed human session into an approved capability is exactly the kind of silent change a regulated environment cannot accept.

---

## 13. Observability and evidence

### 13.1 Structured log — one JSONL event stream per run

```json
{"ts":"2026-08-12T09:14:20.114Z","run_id":"rpl_01J9ZQ8F","seq":14,
 "level":"info","event":"step.completed","step":"s4","action":"click",
 "target_summary":"button name='Find'","rung_used":2,"duration_ms":1890,
 "checkpoint":"passed","lease":"automation","url_digest":"sha256:c1a…"}
```

Event vocabulary: `run.started` · `policy.evaluated` · `policy.blocked` · `observation.captured` · `llm.requested` / `llm.responded` (discovery only, token counts + cassette ref) · `action.dispatched` · `step.completed` · `checkpoint.failed` · `expectation.matched` · `recovery.attempted` · `escalation.raised` · `lease.transferred` · `human.action` · `run.finished`.

### 13.2 Evidence bundle layout

```
evidence/
  discovery/dsc_01J9Z.../
    run.jsonl                 structured log
    trace.zip                 Playwright trace (DOM+network+screenshots)
    observations/s01.ax.json  AX snapshot per step
    screenshots/s01.png
    llm/                      request/response cassettes (redacted)
    artifact.yaml             the compiled output
    result.json
    README.md                 what this run was, how to reproduce
  replay/
    rpl_success/              happy path, 10-run stability report
    rpl_not_found/            business_outcome: MEMBER_NOT_FOUND
    rpl_validation/           business_outcome: VALIDATION_REJECTED
    rpl_session_expired/      hard_failure → escalation → handoff → resume
    rpl_interstitial/         recoverable: dialog dismissed, run completes
    rpl_bad_input/            INVALID_INPUT, failed before step 1
  artifacts/
    cap.member.read_savings_balance.v3.yaml
    cap.member.open_subaccount.v4.yaml
    overlays/tenant_b.patch.yaml
  capability-schema.json      generated JSON Schema
```

Rich failure signal: **screenshot + AX snapshot + Playwright trace** on every hard failure. Trace is the highest-value artifact — it replays the browser state in a viewer, which is what actually shortens debugging.

---

## 14. Heterogeneity and multi-tenant (design)

### 14.1 Surface abstraction — the seam

The artifact describes **intent + semantic target + expected state**. It never describes markup. So the port is:

```python
class Surface(Protocol):
    def observe(self) -> Observation: ...          # ax_tree, screenshot, url, frames, text
    def resolve(self, target: Target) -> Handle: ...   # runs the ladder, returns match + rung
    def act(self, action: Action, handle: Handle | None) -> ActionResult: ...
    def wait(self, condition: Condition, timeout_ms: int) -> bool: ...
    def session_info(self) -> SessionInfo: ...
    def pause(self) -> None; def resume(self) -> None
```

| Surface | Perception | Action | Which ladder rungs work |
|---|---|---|---|
| Modern web (built) | Playwright AX tree | CDP / element handles | 1–5 |
| Legacy web / frameset | same AX tree, per-frame; frame identity in `Target.frame` | same | 1,2,3,4,5 — rung 3 (`table_cell_neighbour`) exists specifically for this |
| Native desktop (Win32/WinForms) | **UIA tree** — same shape as AX: role, name, value | `pywinauto` / UIA patterns, or coordinates | 1,2,5 — no CSS, no tables |
| Citrix / published app / VDI | screenshot + OCR only | coordinate click/type | 5 only |

The reason the ladder is ordered the way it is: **rung 1 and rung 5 are the two rungs that exist on every surface.** Everything between is an optimisation for surfaces that happen to have structure. A capability recorded on web with a healthy rung-1 target is *conceptually* portable to desktop; what changes is the adapter, not the artifact.

What would need to change for desktop: `entry` becomes a process/window spec instead of a URL; `navigate` becomes `focus_window`/`menu_select`; the allowlist becomes process + window-title based instead of domain/route. All additive to the enum, none of it touches the step/target/checkpoint model.

### 14.2 Multi-tenant reuse — base + overlay

**Identity.** A capability is keyed by `(product, product_version, capability_id)`. Tenant is *not* part of identity — it is a resolution input. One recording for CoreVantage 9.4 serves every tenant on CoreVantage 9.4.

**Resolution order at load time (most specific wins):**

```
base(product, product_version)
  ← overlay(product, product_version, tenant)      # RFC 7386 JSON-merge-patch
  ← overlay(product, product_version, tenant, env)
```

**Overlay example — tenant B renamed the button and added a required field:**

```yaml
# artifacts/overlays/tenant_b.patch.yaml
targets: cap.member.open_subaccount@4
tenant: tenant:cu_northlake
patch:
  steps:
    s4:
      target: { strategies: [ { kind: ax_role_name, role: button, name: "Search" } ] }
    s6a:                                  # inserted step
      after: s6
      intent: Select required product code
      action: select
      target: { strategies: [ { kind: ax_role_name, role: combobox, name: "Product Code" } ] }
      value: { from_input: product_code, default: "SAV-01" }
  inputs:
    + { name: product_code, type: string, required: false, default: "SAV-01" }
```

Overlays are **narrow by construction** — they may patch targets, waits, timeouts, expectations, and insert/skip steps; they may **not** change `outputs`, `outcomes`, or `policy.risk_class`, because those are the caller's contract. A tenant that needs a different contract needs a different capability, and the loader enforces that.

**Drift detection with no new infrastructure.** Every replay already reports `rung_used` and `degradations`. Aggregate per `(capability, tenant)`:

- rung inflation (recorded rung 1, now resolving at rung 3) → *this tenant's UI changed*
- rising `AMBIGUOUS_TARGET` → *a new element with the same accessible name appeared*
- rising `UNEXPECTED_STATE` at a specific step → *a new interstitial or validation rule*
- checkpoint latency drift → *performance/version change*

Management policy: a tenant crossing a degradation threshold is flagged for **re-discovery scoped to the failing step**, and the output is a proposed overlay in a PR — never an auto-applied change to an approved capability. Human review stays in the loop because the artifact is the audit object.

**Canonicalisation.** The compiler normalises concrete routes into templates (`/member/100234` → `/member/{member_id}`) and concrete values into inputs at recording time. This is what makes a base artifact portable rather than accidentally tenant-specific; it is also the cheapest of the stretch goals and is in scope.

---

## 15. Repository layout

```
handspan/
  README.md                     setup, keys, demo path, no-live-services mode
  REPORT.md                     the seven required headings
  pyproject.toml
  .env.example
  Makefile                      make app | discover | replay | faults | test | evidence
  docs/
    adr/0001-language.md … 0007-stack.md
    capability-schema.json      generated, committed
  policies/
    corevantage.yaml
    redaction.yaml
  src/handspan/
    cli.py                      discover | replay | operator | validate | catalog
    schema/
      capability.py             Pydantic models — the artifact
      results.py                ReplayResult, InterventionRequest
      conditions.py             Condition / Checkpoint / Expectation
    surface/
      base.py                   Surface protocol, Observation, Action, Target
      web_aria.py               Playwright + AX implementation
      ax_compact.py             AX tree → LLM-sized view
      ladder.py                 locator resolution + rung reporting
    discovery/
      agent.py                  observe→decide→act loop
      prompts.py
      tools.py                  action vocabulary as LLM tool schema
      compiler.py               trace → artifact
      limits.py
    replay/
      executor.py               NO llm/discovery imports (enforced)
      binder.py                 params → typed values
      checkpoints.py
      recovery.py
      loader.py                 artifact load + overlay merge + version gate
    policy/
      allowlist.py  risk.py  redaction.py
    session/
      lease.py  live_session.py
    escalation/
      detector.py  request.py  bus.py (filesystem)
    operator/
      app.py  templates/console.html      mocked UI, real mechanism
    errors/
      taxonomy.py  classifier.py
    obs/
      logger.py  evidence.py
    llm/
      client.py  cassette.py
  targets/legacybank/
    app.py  templates/  faults.py  tenants/{a,b}/  seed.py
  tests/
    unit/  contract/  integration/  e2e/  fixtures/pii_corpus.py
  evidence/                     committed demo evidence
```

---

## 16. Test strategy

### 16.1 Philosophy

Test where a bug would be silent and expensive: schema validation, locator resolution, error classification, redaction, lease transitions. Do not chase coverage on glue.

### 16.2 Test pyramid

| Level | Count (target) | Runs in CI | What |
|---|---|---|---|
| Unit | ~70 | yes | schema validation, ladder resolution, classifier, redaction, binder, lease FSM, overlay merge |
| Contract | ~15 | yes | `ReplayResult` / `InterventionRequest` golden snapshots; JSON Schema backward-compat |
| Integration | ~25 | yes (local app, headless) | replay against `legacybank` with each injected fault |
| E2E discovery | 2 | yes via cassettes; nightly live | full discovery → artifact → replay |
| Architecture | 3 | yes | import boundaries, no `sleep()`, no literal PII in artifacts |

### 16.3 Representative test cases

| ID | Test | Expected |
|---|---|---|
| T-SCH-03 | artifact with unknown `action` | `ValidationError`, names the field |
| T-SCH-09 | artifact with `schema_version: 2.0.0` | load refused, `SCHEMA_INCOMPATIBLE` |
| T-SCH-11 | step containing a literal matching a `pii` input | compiler raises |
| T-LOC-02 | rung 1 removed from page | rung 2 resolves, `degradations` populated |
| T-LOC-05 | two buttons named "Find" | `AMBIGUOUS_TARGET`, no click dispatched |
| T-LOC-07 | element only in `content` frame | resolved via `Target.frame`, not by frame guessing |
| T-ERR-01 | search unknown member | `business_outcome: MEMBER_NOT_FOUND`, exit code 0 |
| T-ERR-04 | submit with missing required field | `business_outcome: VALIDATION_REJECTED` |
| T-ERR-06 | interstitial injected before search | `recoverable: KNOWN_INTERSTITIAL`, run succeeds, recovery logged |
| T-ERR-07 | interstitial injected 3× | recovery bound exceeded → `UNEXPECTED_STATE`, hard failure |
| T-ERR-09 | session expired mid-flow | `SESSION_EXPIRED`, intervention raised, no credential typed |
| T-ERR-11 | app returns 500 | `APP_ERROR` with screenshot + trace |
| T-ERR-12 | unmapped new error banner | `UNEXPECTED_STATE`, never misclassified as success |
| T-REP-01 | `import handspan.replay` with `llm` module removed | imports fine |
| T-REP-04 | replay 10× happy path | identical step path, identical outputs, stability 1.0 |
| T-POL-02 | artifact step navigates to `/admin/users` | `POLICY_BLOCKED` before navigation |
| T-POL-03 | server 302s to a denied route | post-navigation check catches it |
| T-POL-08 | risky `submit_form` in `--unattended` | blocked with justification in result |
| T-POL-09 | risky `submit_form` in `--attended` | intervention raised, human approves, proceeds |
| T-SEC-04 | full suite output scanned for PII corpus | zero hits |
| T-SEC-05 | failure screenshot on a page showing an SSN | SSN region masked |
| T-ESC-03 | dead-end during discovery | intervention with screenshot + AX + `why` |
| T-ESC-06 | executor attempts an action while lease is `HUMAN_HELD` | refused, logged |
| T-ESC-08 | human completes step then releases | resume verifies state, run completes, `human_intervention` step recorded |
| T-ESC-09 | human leaves app in wrong state then releases | `RESUME_STATE_MISMATCH`, clean failure |
| T-ESC-10 | handoff timeout | `TERMINATED`, `abandoned: true` |
| T-MT-02 | base artifact + tenant B overlay | replays on tenant B, patched targets used |
| T-MT-03 | overlay attempting to change `outputs` | loader rejects |

### 16.4 Fault injection matrix (the `legacybank` control plane)

| Fault flag | Simulates | Expected class |
|---|---|---|
| `?fault=slow` | transient slowness | recoverable → success |
| `?fault=dialog` | surprise interstitial | recoverable → success |
| `?fault=notfound` | record not found | business outcome |
| `?fault=validation` | server-side field error | business outcome |
| `?fault=denied` | permission denial | business outcome |
| `?fault=expire` | session timeout | hard failure → escalation |
| `?fault=500` | app error | hard failure |
| `?fault=dupname` | two same-named buttons | hard failure (`AMBIGUOUS_TARGET`) |

All eight are exercised in CI and their results committed to `/evidence/`.

### 16.5 Running without live services

`make test` needs no API key: discovery E2E uses committed LLM cassettes, the target app runs locally. `make discover-live` is the only path needing `ANTHROPIC_API_KEY`. This is stated at the top of `README.md`.

---

## 17. Delivery plan

| Phase | Deliverable | Est. |
|---|---|---|
| 0 | Repo scaffold, ADRs, `make` targets, CI skeleton | 1.5h |
| 1 | `legacybank` app: two tenants, hostility checklist, fault control plane, seed data | 3.5h |
| 2 | Schema (`capability.py`, `results.py`), JSON Schema export, unit tests | 3h |
| 3 | `Surface` port + `WebAriaSurface` + ladder resolver + AX compaction | 3.5h |
| 4 | Replay executor, binder, checkpoints, recovery, error taxonomy, integration tests | 4h |
| 5 | Discovery agent, tool schema, compiler, cassettes; **the real live run** | 4h |
| 6 | Policy: allowlist, risk, redaction + security tests | 2h |
| 7 | Escalation: lease, detector, intervention, operator console mock, resume | 3h |
| 8 | Evidence generation (all 8 faults + stability run), `REPORT.md`, `README.md` | 2.5h |
| 9 | Stretch: capability catalog (`handspan catalog` + typed invoke) and cross-tenant overlay demo | 2h |
| | **Total** | **~29h** (trim phase 9 first if over) |

**Build order rationale:** schema before engines (it is the contract), replay before discovery (replay defines what a valid artifact must contain, so discovery has a target to compile *to* — building discovery first reliably produces artifacts replay cannot execute).

---

## 18. Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Self-built target is unrealistically easy | Undermines the whole submission | Hostility checklist frozen before agent work; never edited to make the agent pass; documented in `REPORT.md` |
| R2 | AX tree too large for context | Discovery fails or costs a lot | Relevance-based compaction (interactive + near-last-action), hard node cap, tested at cap |
| R3 | Model produces plausible but unreplayable steps | Artifact fails on first replay | Closed action vocabulary as tool schema; compiler validates against Pydantic; every discovery run auto-replays once before being accepted |
| R4 | Handoff mechanism turns out to be a demo, not real | Fails a headline evaluation criterion | Bare mode (direct interaction with the persistent context) as the default path — works even if the console UI is skipped |
| R5 | Over-engineering the operator console | Time sink on explicitly out-of-scope work | Hard cap: one HTML file, 2fps screenshot poll, three endpoints |
| R6 | Multi-tenant design drifts into building infrastructure | Brief penalises this | Overlay merge is a loader function + one demo overlay; nothing more |
| R7 | PII leaks into committed evidence | Credibility + the exact thing §3.4 tests | Synthetic data only; redaction at capture; automated scanner gate in CI |
| R8 | Scope creep across nine phases | Nothing finishes | Every phase ends with something committed and demoable; phase 9 is the only optional one |

---

## 19. Stretch goals — picked and justified

Two only, per the brief's "depth over breadth":

1. **Agent-facing capability catalog.** `handspan catalog --json` emits every approved artifact as a function-calling tool definition (name, description, input JSON Schema, output JSON Schema, declared outcomes) generated straight from the Pydantic models; `handspan invoke cap.member.read_savings_balance --member_id 100234` shows one being called. *Why this one:* it closes the loop back to the actual product thesis — capabilities the AI agent invokes on demand — and costs almost nothing because the schema already exists.
2. **Cross-tenant reuse demo.** One base artifact replayed against tenant A and tenant B, the latter through an overlay. *Why:* it turns §14.2 from prose into evidence, and it is the single most credible answer to "hundreds of tenants running the same vendor product."

Explicitly declined: assisted LLM fallback on replay failure (contradicts the determinism guarantee we are selling; escalation is the honest answer), and code generation (a page-object emitter is a nice demo that proves nothing load-bearing).

---

## 20. Cuts (to be written into `REPORT.md` §7)

| Cut | Why | What we would build next |
|---|---|---|
| Desktop/UIA adapter | Port defined; adapter is a week of Windows work for the same conceptual result | UIA `Surface` implementation, `focus_window`/`menu_select` actions, process-based allowlist |
| Real co-browsing console | Explicitly out of scope; mechanism is what matters | WebRTC/CDP-streamed console with per-element permissions and full input audit |
| Queues, workers, concurrency | Brief penalises premature scaling infra | Run executor as a queued worker; lease store → Redis; artifact store → Postgres + catalog API |
| Auth/credential handling | Never type credentials — session-expiry escalates to a human by design | Vault-backed session broker so the *broker* logs in and the agent inherits a session it cannot read |
| Auto-promotion of human handoff actions into artifacts | Unreviewed changes to approved capabilities are unacceptable in regulated systems | Proposed-patch PR flow with reviewer sign-off |
| Multi-run flakiness beyond N=10 | Diminishing signal at this scale | Nightly N=100 per tenant, stability score gating `approved` status |
| Localisation of accessible names | Single-locale assumption in rung 1 | Name-alias tables per locale in the app profile |

---

## 21. Acceptance criteria (definition of done)

**Functional**

- [ ] `make app` starts `legacybank` with tenants A and B and the fault control plane
- [ ] `handspan discover --goal "…" --target http://localhost:8081/servicing/home` completes a real LLM-driven run and writes `artifact.yaml` + evidence
- [ ] `handspan replay --artifact … --input member_id=100234` returns `success` with typed outputs, no LLM imported
- [ ] `--input member_id=999999` returns `business_outcome: MEMBER_NOT_FOUND`, exit code 0
- [ ] Each of the 8 faults produces the classification in §16.4, evidenced
- [ ] A blocked risky action and a blocked out-of-allowlist navigation are both evidenced
- [ ] Session-expiry replay raises an intervention, a human takes the live session, resumes, run completes — evidenced in `handoff.jsonl`
- [ ] 10-run stability report committed
- [ ] Base artifact replays on tenant B via overlay
- [ ] `handspan catalog --json` emits valid tool definitions; one invocation shown

**Quality**

- [ ] `ruff` clean, `mypy --strict` clean on `schema/`, `replay/`, `policy/`
- [ ] Full suite green with no `ANTHROPIC_API_KEY`
- [ ] PII scanner test green
- [ ] Architecture tests green (import boundary, no `sleep()`, no literals in artifacts)

**Documentation**

- [ ] `README.md`: setup, config, no-live-services mode, exact demo commands
- [ ] `REPORT.md`: exactly the seven required headings, 1–3 pages
- [ ] `/evidence/`: artifact + discovery log + replay logs incl. ≥1 error/exceptional state
- [ ] 7 ADRs committed
- [ ] Every mock explicitly labelled with what was mocked and why

---

## 22. Appendix A — mapping to their evaluation criteria

| Their criterion (weighted order) | Where we win it |
|---|---|
| System design | Two named seams (§7.2), closed action vocabulary shared by three consumers (§8.5), ADRs |
| Correctness of core loop | Real discovery run + auto-replay validation + 10-run determinism report |
| Robustness & error handling | 3-class taxonomy with `UNEXPECTED_STATE` as honest default (§10.2), 8-fault matrix, locator ladder with `require_unique` |
| Human-in-the-loop escalation | Lease FSM checked before every action, same persistent context, `resume_contract` state re-verification (§12) |
| Generalisation | Ladder rungs mapped to surface capabilities, base+overlay with contract-preserving restrictions, drift from existing telemetry (§14) |
| Safety & data handling | Pre-flight gate in both engines, fail-closed risky actions with cost-asymmetry justification, redaction at capture + scanner test (§11) |
| Code quality | mypy strict on the load-bearing modules, architecture tests, ~110 tests placed where bugs are silent |
| Communication | `REPORT.md` seven headings, ADRs, explicit cut table with next steps |

## 23. Appendix B — the one-line pitch to defend in interview

> "The artifact is the product. Discovery is a compiler pass that turns an expensive model run into a typed, reviewable capability; replay is a deterministic interpreter for that capability with a three-class error contract; escalation is the escape hatch that keeps determinism honest instead of pretending a model can recover anything. Every extension point in the system — new surface, new tenant, new error — is a data change, not a code change."