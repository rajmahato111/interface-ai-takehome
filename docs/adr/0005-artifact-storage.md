# ADR-005 — Artifact storage: YAML on disk, git-tracked, JSON Schema published

## Decision
Capabilities live as YAML files. JSON Schema is generated from Pydantic and committed. Filesystem only.

## Why
A capability change must show up as a readable PR diff. A database is scaling infrastructure the brief tells us not to build.

## Trade-off
No query/catalog at scale. Noted as a next step; `handspan catalog` is a directory scan.
