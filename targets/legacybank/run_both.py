"""Start tenant A on 8081 and tenant B on 8082 in one process group."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> None:
    env_a = {**os.environ, "LEGACYBANK_TENANT": "a"}
    env_b = {**os.environ, "LEGACYBANK_TENANT": "b"}
    cmd_a = [
        sys.executable,
        "-m",
        "uvicorn",
        "legacybank.app:app",
        "--app-dir",
        "targets",
        "--host",
        "127.0.0.1",
        "--port",
        "8081",
    ]
    cmd_b = [
        sys.executable,
        "-m",
        "uvicorn",
        "legacybank.app:app",
        "--app-dir",
        "targets",
        "--host",
        "127.0.0.1",
        "--port",
        "8082",
    ]
    pa = subprocess.Popen(cmd_a, env=env_a)
    pb = subprocess.Popen(cmd_b, env=env_b)
    print("legacybank A http://127.0.0.1:8081/servicing/home")
    print("legacybank B http://127.0.0.1:8082/servicing/home")

    def stop(*_args: object) -> None:
        pa.terminate()
        pb.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while True:
        if pa.poll() is not None or pb.poll() is not None:
            stop()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
