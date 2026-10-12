"""Persistence (backend-spec §2). SQLite via SQLAlchemy 2; schema managed by Alembic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Run(Base):
    __tablename__ = "run"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    suite_version: Mapped[str] = mapped_column(String(20))
    model_keys: Mapped[list[Any]]
    categories: Mapped[list[Any]]
    tiers: Mapped[list[Any]]
    repeats: Mapped[int] = mapped_column(default=1)
    call_cap: Mapped[int]
    calls_made: Mapped[int] = mapped_column(default=0)
    api_equiv_cost_usd: Mapped[float] = mapped_column(default=0.0)
    params: Mapped[dict[str, Any]]
    judge_rotation: Mapped[dict[str, Any]]
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    results: Mapped[list[Result]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "result"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("run.id"), index=True)
    model_key: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    task_id: Mapped[str] = mapped_column(String(32))
    task_hash: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), index=True)
    tier: Mapped[str] = mapped_column(String(10), index=True)
    attempt: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    response_text: Mapped[str | None] = mapped_column(Text, default=None)
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)
    reasoning_tokens: Mapped[int | None] = mapped_column(default=None)
    cached_tokens: Mapped[int | None] = mapped_column(default=None)
    overhead_tokens: Mapped[int | None] = mapped_column(default=None)
    tokens_estimated: Mapped[dict[str, Any]] = mapped_column(default=dict)
    api_equiv_cost_usd: Mapped[float | None] = mapped_column(default=None)
    latency_ms: Mapped[int | None] = mapped_column(default=None)
    checks: Mapped[list[Any]] = mapped_column(default=list)
    score: Mapped[int | None] = mapped_column(default=None)
    score_source: Mapped[str | None] = mapped_column(String(10), default=None)
    needs_review: Mapped[bool] = mapped_column(default=False)
    review_note: Mapped[str | None] = mapped_column(Text, default=None)
    run: Mapped[Run] = relationship(back_populates="results")
    judge_scores: Mapped[list[JudgeScore]] = relationship(cascade="all, delete-orphan")
    defects: Mapped[list[Defect]] = relationship(cascade="all, delete-orphan")


class JudgeScore(Base):
    __tablename__ = "judge_score"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("result.id"), index=True)
    judge_model_key: Mapped[str] = mapped_column(String(64))
    score: Mapped[int | None] = mapped_column(default=None)
    rationale: Mapped[str | None] = mapped_column(Text, default=None)
    raw_output: Mapped[str | None] = mapped_column(Text, default=None)


class Defect(Base):
    __tablename__ = "defect"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("result.id"), index=True)
    model_key: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32))
    tier: Mapped[str] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(2))
    title: Mapped[str] = mapped_column(String(200))
    expected: Mapped[str | None] = mapped_column(Text, default=None)
    actual: Mapped[str | None] = mapped_column(Text, default=None)
    evidence: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open")


def make_engine(url: str) -> Engine:
    return create_engine(url, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(engine, expire_on_commit=False)
