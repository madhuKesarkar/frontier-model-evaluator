# Frontier Model Evaluator — common commands. Run `make help` for the list.
# Assumes: backend/.venv exists (see backend/README.md) and `npm install` was run in frontend/.

SHELL := /bin/bash
VENV  := backend/.venv/bin
PY    := $(VENV)/python

.PHONY: help setup dev dev-backend dev-frontend lint test ac-check ac-check-strict check

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend (venv) and frontend dependencies
	cd backend && python3.12 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
	cd frontend && npm install --no-audit --no-fund

dev-backend: ## Run the API on http://127.0.0.1:8000
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-frontend: ## Run the UI on http://127.0.0.1:5173 (proxies /api to the backend)
	cd frontend && npm run dev

dev: ## Run backend and frontend together (Ctrl+C stops both)
	@trap 'kill 0' INT TERM EXIT; $(MAKE) -s dev-backend & $(MAKE) -s dev-frontend & wait

lint: ## Lint and type-check everything
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy .
	cd frontend && npm run -s lint && npm run -s typecheck

test: ## Run all tests
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test -s

ac-check: ## Report which demo acceptance criteria have tests
	@$(PY) scripts/ac_check.py

ac-check-strict: ## Fail if any demo acceptance criterion has no test
	@$(PY) scripts/ac_check.py --strict

check: lint test ac-check ## Everything CI runs
