# frontend

React + TypeScript (Vite) app. Governed by `specs/frontend-spec.md` and `specs/api-contract-spec.md`.

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173 (proxies /api to the backend on :8000)

npm run lint && npm run typecheck && npm test   # checks (CLAUDE.md)
```

Start the backend first (see `backend/README.md`) to see "Backend connected".
