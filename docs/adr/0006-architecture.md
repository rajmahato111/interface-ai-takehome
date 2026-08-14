# ADR-006 — Architecture: single process, library-first, three CLI entry points

## Decision
No services, queues, or workers. `handspan discover | replay | operator`. The only cross-process need is human handoff: a long-lived browser process plus a file-backed lease.

## Why
Simpler is fine if justified. Every module is import-clean so it can be lifted into a worker later.

## Trade-off
No concurrency story. Explicitly a next step.
