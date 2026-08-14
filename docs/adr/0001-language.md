# ADR-001 — Language & runtime: Python 3.12

## Decision
Python 3.12 with Pydantic v2 as the artifact schema, Playwright Python as the driver.

## Why
The artifact is the product. Pydantic gives typed models, validation, and JSON Schema export in one place. Playwright's Python API is first-class. Calling agents in this domain are Python-heavy.

## Trade-off
Node would share a runtime with browser glue. Not worth losing Pydantic.
