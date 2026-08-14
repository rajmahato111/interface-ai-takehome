# Handspan

Record-once / replay-many UI automation for legacy bank back-office screens.

The **capability artifact** is the product. Discovery is how it gets written (LLM in the loop, once). Replay is how it gets used (no LLM). Escalation is what happens when neither can finish safely.

## Setup

```bash
python3.12 -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env   # ANTHROPIC_API_KEY only needed for live discovery
```

No API key is required for `make test`. Discovery CI uses a recorded cassette.

## Demo path

```bash
make app                 # tenant A :8081, tenant B :8082
make replay              # typed success, no LLM imported
handspan replay --artifact evidence/artifacts/cap.member.read_savings_balance.yaml \
  --input member_id=999999
handspan catalog --json
handspan invoke cap.member.read_savings_balance --member_id 100234
```

Live discovery (needs `ANTHROPIC_API_KEY`):

```bash
make discover-live
```

Cassette discovery (no key):

```bash
make discover
```

## No-live-services mode

`make test` boots `legacybank` in-process, drives Chromium headless, and replays the cassette. It does not call Anthropic.

## Layout

See `PRD.md` §15. Target app hostility checklist is frozen in `targets/legacybank/HOSTILITY.md`.

## Operator console

Mocked UI, real seam. `handspan operator` serves a screenshot poller that clicks/types into the **same** Playwright page the executor paused. Bare mode: interact with the headed window and `POST /operator/{session}/release`.
