# backend

FastAPI app and evaluation engine. Governed by `specs/backend-spec.md` and `specs/api-contract-spec.md`.

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app --host 127.0.0.1 --port 8000   # run
ruff check . && mypy . && pytest                     # checks (CLAUDE.md)
```
