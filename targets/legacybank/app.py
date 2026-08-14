"""Deliberately hostile credit-union servicing console."""

from __future__ import annotations

import os
import random
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from legacybank.seed import MEMBERS, USERS
from legacybank.tenants import TENANTS

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
IDLE = int(os.environ.get("LEGACYBANK_IDLE_SECONDS", "60"))
LATENCY = os.environ.get("LEGACYBANK_LATENCY", "1") != "0"


def _tenant_id() -> str:
    return os.environ.get("LEGACYBANK_TENANT", "a")


def tenant() -> dict[str, Any]:
    return TENANTS[_tenant_id()]


def fid(suffix: str) -> str:
    return f"{tenant()['id_prefix']}_{suffix}"


def create_app(tenant_id: str | None = None) -> FastAPI:
    tid = tenant_id or os.environ.get("LEGACYBANK_TENANT", "a")
    app = FastAPI(title=f"legacybank-{tid}", docs_url=None, redoc_url=None)
    app.state.tenant_id = tid

    def current_tenant() -> dict[str, Any]:
        return TENANTS[app.state.tenant_id]

    def current_fid(suffix: str) -> str:
        return f"{current_tenant()['id_prefix']}_{suffix}"

    @app.middleware("http")
    async def latency_and_idle(request: Request, call_next):  # type: ignore[no-untyped-def]
        if LATENCY and not request.url.path.startswith("/health"):
            lo, hi = 0.05, 0.25
            if request.session.get("fault") == "slow":
                lo, hi = 0.4, 0.8
            time.sleep(random.uniform(lo, hi))
        fault_q = request.query_params.get("fault")
        if fault_q:
            request.session["fault"] = fault_q
        if request.url.path not in ("/login", "/health", "/favicon.ico") and request.session.get(
            "user"
        ):
            last = float(request.session.get("last_seen") or 0)
            if last and (time.time() - last) > IDLE:
                request.session.clear()
                request.session["expired"] = True
            else:
                request.session["last_seen"] = time.time()
        if request.session.get("fault") == "expire" and request.url.path.startswith("/member"):
            request.session.clear()
            request.session["expired"] = True
        return await call_next(request)

    def html(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        t = current_tenant()
        return TEMPLATES.TemplateResponse(
            request,
            name,
            {
                "request": request,
                "t": t,
                "fid": current_fid,
                "fault": request.session.get("fault"),
                **ctx,
            },
        )

    def require_login(request: Request) -> RedirectResponse | None:
        if request.session.get("expired"):
            request.session.clear()
            return RedirectResponse("/login?expired=1", status_code=303)
        if not request.session.get("user"):
            from urllib.parse import quote

            nxt = request.url.path
            if request.url.query:
                nxt += "?" + request.url.query
            return RedirectResponse(f"/login?next={quote(nxt, safe='')}", status_code=303)
        return None

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "1", "tenant": app.state.tenant_id}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse("/servicing/home", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    def login_get(request: Request) -> HTMLResponse:
        return html(
            request, "login.html", error=None, expired=request.query_params.get("expired") == "1"
        )

    @app.post("/login", response_class=HTMLResponse)
    def login_post(
        request: Request, username: str = Form(...), password: str = Form(...)
    ) -> Response:
        user = USERS.get(username)
        if not user or user["password"] != password:
            return html(request, "login.html", error="Invalid credentials", expired=False)
        fault = request.session.get("fault")
        request.session.clear()
        request.session["user"] = username
        request.session["role"] = user["role"]
        request.session["last_seen"] = time.time()
        request.session["sid"] = secrets.token_hex(8)
        if fault:
            request.session["fault"] = fault
        dest = request.query_params.get("next") or "/servicing/home"
        return RedirectResponse(dest, status_code=303)

    @app.get("/logout")
    def logout(request: Request) -> RedirectResponse:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/servicing/home", response_class=HTMLResponse)
    def home(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "frameset.html")

    @app.get("/servicing/nav", response_class=HTMLResponse)
    def nav(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "nav.html")

    @app.get("/servicing/welcome", response_class=HTMLResponse)
    def welcome(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "welcome.html")

    @app.get("/servicing/postback")
    def postback(request: Request, t: str = "") -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        mapping = {
            "mbrSearch": "/member/search",
            "home": "/servicing/welcome",
            "newSub": "/subaccount/new",
        }
        return RedirectResponse(mapping.get(t, "/servicing/welcome"), status_code=302)

    @app.get("/member/search", response_class=HTMLResponse)
    def search_get(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        if request.session.get("fault") == "500":
            return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)
        return html(
            request,
            "search.html",
            not_found=False,
            dialog=request.session.get("fault") == "dialog",
            dupname=request.session.get("fault") == "dupname",
            member_id="",
        )

    @app.post("/member/search", response_class=HTMLResponse)
    async def search_post(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        if request.session.get("fault") == "500":
            return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)
        form = await request.form()
        member_id = _pick_member_id(form)
        fault = request.session.get("fault")
        dialog = fault == "dialog"
        dupname = fault == "dupname"
        if fault == "notfound" or member_id not in MEMBERS:
            return html(
                request,
                "search.html",
                not_found=True,
                dialog=dialog,
                dupname=dupname,
                member_id=member_id,
            )
        return RedirectResponse(f"/member/{member_id}", status_code=303)

    @app.get("/member/{member_id}", response_class=HTMLResponse)
    def member_detail(request: Request, member_id: str) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        if request.session.get("fault") == "500":
            return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)
        rec = MEMBERS.get(member_id)
        if not rec:
            return html(
                request,
                "search.html",
                not_found=True,
                dialog=False,
                dupname=False,
                member_id=member_id,
            )
        if request.session.get("role") == "denied" or request.session.get("fault") == "denied":
            return html(request, "denied.html", member_id=member_id)
        return html(request, "detail.html", member_id=member_id, rec=rec)

    @app.get("/subaccount/new", response_class=HTMLResponse)
    def sub_new_get(request: Request, member_id: str = "100234") -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "subaccount.html", member_id=member_id, error=None)

    @app.post("/subaccount/new", response_class=HTMLResponse)
    async def sub_new_post(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        form = await request.form()
        member_id = str(form.get("member_id") or "100234")
        nickname = str(form.get(current_fid("txtNick")) or form.get("nickname") or "")
        amount = str(form.get(current_fid("txtAmt")) or form.get("amount") or "")
        product = str(form.get(current_fid("cboProd")) or form.get("product_code") or "")
        if request.session.get("fault") == "validation" or not nickname or not amount:
            msg = (
                "Product code required"
                if current_tenant()["require_product_code"]
                else "All fields are required"
            )
            return html(request, "subaccount.html", member_id=member_id, error=msg)
        if current_tenant()["require_product_code"] and not product:
            return html(
                request, "subaccount.html", member_id=member_id, error="Product code required"
            )
        q = urlencode({"member_id": member_id, "nickname": nickname})
        return RedirectResponse(f"/subaccount/confirm?{q}", status_code=303)

    @app.get("/subaccount/confirm", response_class=HTMLResponse)
    def sub_confirm(request: Request, member_id: str = "", nickname: str = "") -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "confirm.html", member_id=member_id, nickname=nickname)

    @app.get("/admin/users", response_class=HTMLResponse)
    def admin_users(request: Request) -> Response:
        if (redir := require_login(request)) is not None:
            return redir
        return html(request, "admin.html")

    app.add_middleware(SessionMiddleware, secret_key=os.environ.get("LEGACYBANK_SECRET", "dev"))
    return app


def _pick_member_id(form: Any) -> str:
    for k, v in form.items():
        key = str(k).lower()
        if "txt1" in key or key.endswith("q") or "memberid" in key or "member_id" in key:
            return str(v).strip()
    for v in form.values():
        s = str(v).strip()
        if s.isdigit() and len(s) == 6:
            return s
    return ""


app = create_app()
