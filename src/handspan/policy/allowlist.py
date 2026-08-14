"""Declarative allowlist — pre-flight gate on every action."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from ruamel.yaml import YAML

from handspan.errors.taxonomy import Code, HardFailure


@dataclass
class Allowlist:
    domains: list[str]
    allow_routes: list[str]
    deny_routes: list[str]
    allow_actions: list[str]
    deny_actions: list[str]
    max_steps: int = 25
    max_runtime_ms: int = 180000
    forbid_typing_into: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> Allowlist:
        data = YAML(typ="safe").load(Path(path).read_text()) or {}
        routes = data.get("routes") or {}
        actions = data.get("actions") or {}
        limits = data.get("limits") or {}
        extra = data.get("data") or {}
        return cls(
            domains=list(data.get("domains") or []),
            allow_routes=list(routes.get("allow") or ["/**"]),
            deny_routes=list(routes.get("deny") or []),
            allow_actions=list(actions.get("allow") or []),
            deny_actions=list(actions.get("deny") or []),
            max_steps=int(limits.get("max_steps") or 25),
            max_runtime_ms=int(limits.get("max_runtime_ms") or 180000),
            forbid_typing_into=list(extra.get("forbid_typing_into") or []),
        )

    def check_action(self, action: str) -> None:
        if action in self.deny_actions or (
            self.allow_actions
            and action not in self.allow_actions
            and action not in ("extract", "assert", "wait_for", "finish", "escalate")
        ):
            raise HardFailure(Code.POLICY_BLOCKED, f"action {action} denied")

    def check_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        if self.domains and not any(_host_ok(host, d) for d in self.domains):
            raise HardFailure(Code.POLICY_BLOCKED, f"host {host} not allowlisted")
        path = parsed.path or "/"
        if any(_glob(path, g) for g in self.deny_routes):
            raise HardFailure(Code.POLICY_BLOCKED, f"route {path} denied")
        if self.allow_routes and not any(_glob(path, g) for g in self.allow_routes):
            raise HardFailure(Code.POLICY_BLOCKED, f"route {path} not allowlisted")


def _host_ok(netloc: str, pattern: str) -> bool:
    netloc = netloc.lower()
    pattern = pattern.lower()
    if netloc == pattern:
        return True
    host = netloc.split(":")[0]
    phost, _, pport = pattern.partition(":")
    if phost.startswith("*."):
        return host.endswith(phost[1:]) or host == phost[2:]
    if host != phost:
        return False
    if not pport:
        return True
    return netloc.partition(":")[2] == pport


def _glob(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/") or path.startswith(prefix)
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        rest = path[len(prefix) :].lstrip("/")
        return path.startswith(prefix) and "/" not in rest
    return path == pattern
