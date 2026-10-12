"""Write backend/openapi.json from the FastAPI app (the machine-readable API contract).

Run after a *reviewed* change to specs/api-contract-spec.md:  make openapi
tests/test_api.py fails if the code's API and this snapshot disagree (contract drift).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

settings = Settings(
    models_file=ROOT / "config/models.demo.yaml",
    suite_dir=ROOT / "suite/v1",
    database_url="sqlite:///:memory:",
    read_only=False,
    sandbox_image="unused",
)
out = ROOT / "backend/openapi.json"
out.write_text(json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {out.relative_to(ROOT)}")
