# ADR-004 — Target application: local legacybank

## Decision
Build a local credit-union servicing console (FastAPI + Jinja) with two tenant variants and a `?fault=` control plane.

## Why
We need framesets, hostile markup, deterministic faults, a second tenant, and hermetic CI. No public demo site provides that.

## Trade-off
We could accidentally make the target easy. Mitigation: hostility checklist is frozen in `targets/legacybank/HOSTILITY.md` and is not edited to make a failing agent pass.
