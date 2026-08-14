from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from legacybank.app import create_app

os.environ.setdefault("LEGACYBANK_LATENCY", "0")
os.environ.setdefault("LEGACYBANK_IDLE_SECONDS", "120")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _boot(tenant: str) -> tuple[uvicorn.Server, str]:
    port = _free_port()
    app = create_app(tenant)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            if httpx.get(url + "/health", timeout=0.2).status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    return server, url


@pytest.fixture(scope="session")
def bank_a() -> Iterator[str]:
    server, url = _boot("a")
    yield url
    server.should_exit = True


@pytest.fixture(scope="session")
def bank_b() -> Iterator[str]:
    server, url = _boot("b")
    yield url
    server.should_exit = True
