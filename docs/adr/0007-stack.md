# ADR-007 — Full stack

Runtime: Python 3.12, pip-installable package (`uv` optional).
Schema: Pydantic v2, JSON Schema export.
Browser: Playwright Chromium (headed for handoff, headless for CI).
LLM: Anthropic Python SDK, tool-use, temperature 0.
CLI: Typer + Rich.
Target app: FastAPI + Jinja2, session cookies.
Operator console: FastAPI + one HTML page (screenshot poll + click/type forward). Mocked UI, real seam.
Logging: structlog → JSONL.
YAML: ruamel.yaml.
Testing: pytest, syrupy snapshots. Discovery CI uses LLM cassettes.
Lint/type: ruff; mypy strict on `schema/`, `replay/`, `policy/`.
CI: GitHub Actions, no API key required.
