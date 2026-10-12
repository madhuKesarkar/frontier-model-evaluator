"""FastAPI application entry point.

Run locally (binds to localhost only, per backend-spec §1):
    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI

from app.api import health
from app.settings import assert_no_paid_keys

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    assert_no_paid_keys()  # BE-R1: refuse to start with a paid API key in the environment
    application = FastAPI(title="Frontier Model Evaluator", version="0.1.0")
    application.include_router(health.router, prefix=API_PREFIX)
    return application


app = create_app()
