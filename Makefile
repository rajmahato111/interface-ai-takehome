PYTHON ?= python3
export PYTHONPATH := src:targets:$(PYTHONPATH)

.PHONY: app app-a app-b install test lint typecheck discover discover-live replay faults evidence catalog schema

install:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m playwright install chromium

app-a:
	LEGACYBANK_TENANT=a LEGACYBANK_IDLE_SECONDS=$${LEGACYBANK_IDLE_SECONDS:-60} \
		$(PYTHON) -m uvicorn legacybank.app:app --app-dir targets --host 127.0.0.1 --port 8081

app-b:
	LEGACYBANK_TENANT=b LEGACYBANK_IDLE_SECONDS=$${LEGACYBANK_IDLE_SECONDS:-60} \
		$(PYTHON) -m uvicorn legacybank.app:app --app-dir targets --host 127.0.0.1 --port 8082

app:
	$(PYTHON) targets/legacybank/run_both.py

lint:
	$(PYTHON) -m ruff check src targets tests
	$(PYTHON) -m ruff format --check src targets tests

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q

schema:
	$(PYTHON) -m handspan.schema.export

discover:
	$(PYTHON) -m handspan discover --cassette tests/fixtures/cassettes/read_savings.json --goal "Look up member 100234 and read their current savings balance." --target http://127.0.0.1:8081/servicing/home

discover-live:
	$(PYTHON) -m handspan discover --live \
		--cassette evidence/discovery/dsc_live/cassette.json \
		--evidence-dir evidence/discovery/dsc_live \
		--goal "Look up member 100234 and read their current savings balance." \
		--target http://127.0.0.1:8081/servicing/home

replay:
	$(PYTHON) -m handspan replay --artifact evidence/artifacts/cap.member.read_savings_balance.yaml --input member_id=100234

faults:
	$(PYTHON) -m pytest -q tests/integration/test_fault_matrix.py

evidence:
	$(PYTHON) -m pytest -q tests/integration tests/e2e
	$(PYTHON) scripts/write_stability_report.py

catalog:
	$(PYTHON) -m handspan catalog --json
