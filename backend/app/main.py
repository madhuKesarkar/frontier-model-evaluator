"""FastAPI application entry point.

Run locally (binds to localhost only, per backend-spec §1):
    uvicorn app.main:app --host 127.0.0.1 --port 8000
Deployed demo (D-13): FME_READ_ONLY=1 and FME_CORS_ORIGINS=<the Netlify origin>.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health, routes
from app.db import make_engine, make_session_factory
from app.registry import load_registry
from app.settings import Settings, assert_no_paid_keys
from app.suite import load_suite

API_PREFIX = "/api/v1"
READ_ONLY_ALLOWED = {("POST", f"{API_PREFIX}/fit")}  # pure calculation, writes nothing


def create_app(settings: Settings | None = None) -> FastAPI:
    assert_no_paid_keys()  # BE-R1: refuse to start with a paid API key in the environment
    settings = settings or Settings.from_env()
    application = FastAPI(title="Frontier Model Evaluator", version="0.2.0")
    application.state.settings = settings
    application.state.sessions = make_session_factory(make_engine(settings.database_url))
    # A fresh clone has no config/models.yaml yet: start with an empty registry rather than
    # crash; an *invalid* registry still fails loudly (BE-AC-02).
    models = load_registry(settings.models_file) if settings.models_file.exists() else []
    application.state.models = {m.key: m for m in models}
    application.state.tasks = {t.task_id: t for t in load_suite(settings.suite_dir)}

    origins = [o.strip() for o in os.environ.get("FME_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:  # deployed demo: only the Netlify origin may call the API (api-contract §1)
        application.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )  # fmt: skip

    if settings.read_only:

        @application.middleware("http")
        async def read_only_guard(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            method, path = request.method, request.url.path
            if method in {"GET", "HEAD", "OPTIONS"} or (method, path) in READ_ONLY_ALLOWED:
                return await call_next(request)
            return JSONResponse({"detail": "This demo is read-only"}, status_code=405)

    application.include_router(health.router, prefix=API_PREFIX)
    application.include_router(routes.router, prefix=API_PREFIX)
    return application


def _app_from_env() -> FastAPI:
    return create_app()


app = _app_from_env()
