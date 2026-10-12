"""Demo API against the contract (api-contract-spec §1-§4: API-AC-01..04, read-only, CORS)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.fixture import FixtureAdapter
from app.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.registry import load_registry
from app.runner import EvaluationRunner, RunConfig
from app.settings import REPO_ROOT, Settings
from app.suite import load_suite
from tests.test_runner import PassingRunner
from tests.test_security import KEY_PATTERNS

DEMO_MODELS = REPO_ROOT / "config/models.demo.yaml"
OPENAPI_SNAPSHOT = REPO_ROOT / "backend/openapi.json"
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def settings_for(tmp_path: Path, read_only: bool = False) -> Settings:
    return Settings(
        models_file=DEMO_MODELS, suite_dir=REPO_ROOT / "suite/v1",
        database_url=f"sqlite:///{tmp_path / 'api.db'}", read_only=read_only,
        sandbox_image="unused",
    )  # fmt: skip


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """A database holding one synthetic demo run (recorded fixtures, stand-in code runner)."""
    tmp = tmp_path_factory.mktemp("api")
    settings = settings_for(tmp)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    demo = REPO_ROOT / "backend/fixtures/demo"
    adapters = {k: FixtureAdapter.from_dir(demo / k) for k in ("demo-claude", "demo-gpt")}
    runner = EvaluationRunner(
        make_session_factory(engine), load_registry(DEMO_MODELS), load_suite(settings.suite_dir),
        dict(adapters), PassingRunner(), sleep=lambda _: None,
    )  # fmt: skip
    runner.start(RunConfig(["demo-claude", "demo-gpt"], call_cap=200,
                           params={"label": "synthetic-demo", "source": "recorded"}))  # fmt: skip
    return settings


@pytest.fixture
def client(seeded: Settings) -> TestClient:
    return TestClient(create_app(seeded))


def all_responses(client: TestClient) -> list[tuple[str, Any]]:
    """Every demo endpoint, for whole-API checks."""
    out: list[tuple[str, Any]] = []
    for path in ["/models", "/leaderboard", "/models/demo-gpt", "/models/demo-gpt/defects",
                 "/models/demo-gpt/results", "/profile-templates"]:  # fmt: skip
        out.append((path, client.get(f"/api/v1{path}").json()))
    first = out[4][1][0]["result_id"]
    out.append((f"/results/{first}", client.get(f"/api/v1/results/{first}").json()))
    out.append(
        ("/fit", client.post("/api/v1/fit", json={"profile_id": "tpl-code-assistant"}).json())
    )
    return out


# ---------------------------------------------------------------- API-AC-01: shapes
def test_API_AC01_leaderboard_shape(client: TestClient) -> None:
    body = client.get("/api/v1/leaderboard").json()
    assert body["run_source"] == "recorded" and body["run_label"] == "synthetic-demo"
    assert [r["model"]["key"] for r in body["rows"]] == ["demo-claude", "demo-gpt"]
    row = body["rows"][0]
    assert set(row) == {"model", "overall", "scores", "avg_cost_per_task_usd", "p50_latency_ms",
                        "open_s1_s2_defects"}  # fmt: skip
    assert [c["category"] for c in row["scores"]] == [
        "code_generation", "reasoning", "structured_output", "test_design", "long_context",
        "tool_use",
    ]  # fmt: skip
    assert all(1 <= c["score"] <= 5 for c in row["scores"])  # FE-AC-01 data: 1-5 per category
    assert set(row["scores"][0]["by_tier"]) == {"simple", "mid", "complex"}


def test_API_AC01_leaderboard_tier_and_category_filters(client: TestClient) -> None:
    body = client.get("/api/v1/leaderboard?tier=complex&category=tool_use").json()
    gpt = next(r for r in body["rows"] if r["model"]["key"] == "demo-gpt")
    [cell] = gpt["scores"]
    assert cell["category"] == "tool_use" and cell["score"] == 1.0  # refund before receipt (S1)


def test_API_AC01_model_detail_shape(client: TestClient) -> None:
    body = client.get("/api/v1/models/demo-claude").json()
    assert body["model"]["display_name"] == "Demo Claude (synthetic)"
    assert set(body["tokens_by_tier"]) == {"simple", "mid", "complex"}
    simple = body["tokens_by_tier"]["simple"]["avg"]
    assert simple["input_tokens"] > 0 and simple["overhead_tokens"] == 2600
    assert simple["reasoning_tokens"] is None  # BE-AC-17 / FE-AC-04: n/a, not 0
    assert len(body["costliest_task_ids"]) == 3


def test_API_AC01_defects_with_filters_and_evidence(client: TestClient) -> None:
    body = client.get("/api/v1/models/demo-gpt/defects?severity=S1&tier=complex").json()
    assert body["count"] == len(body["items"]) >= 1
    assert all(d["severity"] == "S1" and d["tier"] == "complex" for d in body["items"])
    ev = body["items"][0]["evidence"]
    assert ev["prompt_excerpt"] and ev["response_excerpt"]  # SM-6: evidence present


def test_API_AC01_results_and_result_detail(client: TestClient) -> None:
    rows = client.get("/api/v1/models/demo-gpt/results?category=tool_use").json()
    assert [r["task_id"] for r in rows] == ["TU-C-01", "TU-M-01", "TU-S-01"]
    detail = client.get(f"/api/v1/results/{rows[0]['result_id']}").json()
    assert detail["task"]["task_id"] == "TU-C-01" and len(detail["task"]["content_hash"]) == 64
    assert detail["judges"][0]["judge_model_key"] == "demo-claude"  # cross-provider judge
    assert detail["score"] == 1 and detail["defects"]


def test_API_AC01_profile_templates_and_fit(client: TestClient) -> None:
    templates = client.get("/api/v1/profile-templates").json()
    assert [t["id"] for t in templates] == ["tpl-test-case-gen", "tpl-support-chatbot",
                                            "tpl-code-assistant"]  # fmt: skip
    body = client.post("/api/v1/fit", json={"profile_id": "tpl-support-chatbot"}).json()
    verdicts = {v["model_key"]: v for v in body["verdicts"]}
    gpt = verdicts["demo-gpt"]
    assert gpt["verdict"] == "not_recommended"  # S1 in must-have Tool Use and Long-Context
    assert gpt["cited_defect_ids"] and any(r["rule"] == "s1_in_must_have" for r in gpt["reasons"])
    assert body["verdicts"][0]["model_key"] == "demo-claude"  # best verdict first


def test_fit_with_custom_profile(client: TestClient) -> None:
    profile = {"name": "Reasoning only", "weights": {"reasoning": 5},
               "tier_mix": {"simple": 0, "mid": 100, "complex": 0}}  # fmt: skip
    body = client.post("/api/v1/fit", json={"profile": profile}).json()
    claude = next(v for v in body["verdicts"] if v["model_key"] == "demo-claude")
    assert claude["fit_score"] == 2.0  # RA-M-01: forgot the discount


def test_openapi_snapshot_matches_code() -> None:
    """Contract drift guard: regenerate with `make openapi` after a reviewed contract change."""
    generated = create_app(settings_for(Path("/nonexistent"))).openapi()
    committed = json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))
    assert generated == committed, "API changed: review the contract, then run `make openapi`"


# ---------------------------------------------------------------- API-AC-02: failures
@pytest.mark.parametrize(
    "path",
    ["/models/nope", "/models/demo-gpt?run_id=999", "/leaderboard?run_id=999", "/results/999999",
     "/models/nope/defects", "/models/nope/results"],
)  # fmt: skip
def test_API_AC02_not_found(client: TestClient, path: str) -> None:
    response = client.get(f"/api/v1{path}")
    assert response.status_code == 404 and response.json() == {"detail": "Not found"}


@pytest.mark.parametrize(
    "path",
    ["/leaderboard?tier=huge", "/leaderboard?category=poetry",
     "/models/demo-gpt/defects?severity=S9", "/models/demo-gpt/defects?type=BOGUS"],
)  # fmt: skip
def test_API_AC02_bad_enum_is_422(client: TestClient, path: str) -> None:
    response = client.get(f"/api/v1{path}")
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list) and "loc" in response.json()["detail"][0]


@pytest.mark.parametrize(
    "body,fragment",
    [({"profile": {"name": "x", "weights": {"reasoning": 3},
                   "tier_mix": {"simple": 50, "mid": 30, "complex": 10}}}, "total 100"),
     ({"profile": {"name": "x", "weights": {"reasoning": 0},
                   "tier_mix": {"simple": 100}}}, "above 0"),
     ({"profile_id": "tpl-code-assistant", "profile": {"name": "x"}}, "exactly one"),
     ({}, "exactly one")],
)  # fmt: skip
def test_API_AC02_invalid_profile_is_400(
    client: TestClient, body: dict[str, Any], fragment: str
) -> None:
    response = client.post("/api/v1/fit", json=body)
    assert response.status_code == 400 and fragment in response.json()["detail"]


def test_unknown_template_is_404(client: TestClient) -> None:
    assert client.post("/api/v1/fit", json={"profile_id": "tpl-nope"}).status_code == 404


def test_unmigrated_database_is_503(tmp_path: Path) -> None:
    client = TestClient(create_app(settings_for(tmp_path)))
    response = client.get("/api/v1/leaderboard")
    assert response.status_code == 503 and "make migrate" in response.json()["detail"]


def test_empty_database_gives_empty_leaderboard(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    Base.metadata.create_all(make_engine(settings.database_url))
    body = TestClient(create_app(settings)).get("/api/v1/leaderboard").json()
    assert body == {"run_id": None, "run_label": None, "run_source": None, "rows": []}


# ---------------------------------------------------------------- API-AC-03 / 04
def _walk(value: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _walk(v, f"{path}.{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _walk(v, f"{path}[{i}]")]
    return [(path, value)]


def test_API_AC03_every_timestamp_is_utc_with_z(client: TestClient) -> None:
    stamps = [(p, v) for _, body in all_responses(client) for p, v in _walk(body)
              if p.endswith("_at") and v is not None]  # fmt: skip
    assert stamps, "expected at least one timestamp (last_run_at)"
    assert all(ISO_Z.match(v) for _, v in stamps), stamps


def test_API_AC04_no_secret_in_any_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = "-".join(["sk", "proj", "Z9" * 20])  # built at runtime
    monkeypatch.setenv("SOME_UNRELATED_TOKEN", fake)
    text = json.dumps([body for _, body in all_responses(client)])
    assert fake not in text
    assert not any(p.search(text) for p in KEY_PATTERNS)


# ---------------------------------------------------------------- read-only mode and CORS
def test_read_only_mode_allows_reads_and_fit_only(seeded: Settings) -> None:
    ro = Settings(**{**seeded.__dict__, "read_only": True})
    client = TestClient(create_app(ro))
    assert client.get("/api/v1/leaderboard").status_code == 200
    assert client.post("/api/v1/fit", json={"profile_id": "tpl-code-assistant"}).status_code == 200
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/v1/models")
        assert response.status_code == 405 and response.json()["detail"] == "This demo is read-only"


def test_cors_allows_only_configured_origin(
    seeded: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FME_CORS_ORIGINS", "https://fme-demo.netlify.app")
    client = TestClient(create_app(seeded))
    ok = client.get("/api/v1/health", headers={"Origin": "https://fme-demo.netlify.app"})
    bad = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://fme-demo.netlify.app"
    assert "access-control-allow-origin" not in bad.headers
