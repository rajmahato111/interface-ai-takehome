"""Mock operator UI over a real Playwright session + lease file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from handspan.session.lease import Lease, LeaseState

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
SESSIONS: dict[str, Any] = {}
LEASE_ROOT = Path("evidence/operator")


def create_app() -> FastAPI:
    app = FastAPI(title="handspan-operator")

    @app.get("/operator/{session_id}", response_class=HTMLResponse)
    def console(request: Request, session_id: str) -> HTMLResponse:
        lease = _lease(session_id)
        return TEMPLATES.TemplateResponse(
            request,
            "console.html",
            {"session_id": session_id, "lease": lease.state().value},
        )

    @app.get("/operator/{session_id}/shot")
    def shot(session_id: str) -> Response:
        page = SESSIONS.get(session_id)
        if page is None:
            return Response(b"", media_type="image/png")
        return Response(page.screenshot(), media_type="image/png")

    class Click(BaseModel):
        x: float
        y: float
        w: float
        h: float

    @app.post("/operator/{session_id}/click")
    def click(session_id: str, body: Click) -> dict[str, str]:
        page = SESSIONS.get(session_id)
        if page is None:
            return {"ok": "0"}
        vp = page.viewport_size or {"width": 1280, "height": 800}
        page.mouse.click(body.x / body.w * vp["width"], body.y / body.h * vp["height"])
        _handoff(session_id, "click")
        return {"ok": "1"}

    @app.post("/operator/{session_id}/type")
    def type_(session_id: str, text: str = Form("")) -> RedirectResponse:
        page = SESSIONS.get(session_id)
        if page is not None and text:
            page.keyboard.type(text)
            _handoff(session_id, "type")
        return RedirectResponse(f"/operator/{session_id}", status_code=303)

    @app.post("/operator/{session_id}/release")
    def release(session_id: str) -> RedirectResponse:
        lease = _lease(session_id)
        if lease.state() == LeaseState.HUMAN_HELD:
            lease.transition(LeaseState.RESUME_REQUESTED)
        return RedirectResponse(f"/operator/{session_id}", status_code=303)

    return app


def register(session_id: str, page: Any, lease_path: Path | None = None) -> None:
    SESSIONS[session_id] = page
    if lease_path:
        LEASE_ROOT.mkdir(parents=True, exist_ok=True)
        (LEASE_ROOT / f"{session_id}.path").write_text(str(lease_path))


def _lease(session_id: str) -> Lease:
    marker = LEASE_ROOT / f"{session_id}.path"
    path = Path(marker.read_text()) if marker.exists() else LEASE_ROOT / f"{session_id}.json"
    return Lease(path, session_id)


def _handoff(session_id: str, action: str) -> None:
    p = Path("evidence/operator") / session_id / "handoff.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.open("a").write(f'{{"action":"{action}","redacted":true}}\n')


app = create_app()
