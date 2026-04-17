# MiroFish — Agent Guide

## Stack

- **Frontend**: Vue 3 + Vite (port 3000), proxied API to backend
- **Backend**: Python Flask (port 5001), uv for dependency management
- **Simulation engine**: OASIS (camel-ai) for multi-agent social simulation
- **Memory**: Zep Cloud for agent memory
- **Graph DB**: Neo4j (optional)
- **Python**: 3.11–3.12 only

## Dev Commands

```bash
# One-time setup
npm run setup:all          # npm deps + uv sync

# Run dev (both services)
npm run dev                # starts frontend + backend via concurrently

# Run separately
npm run backend            # cd backend && uv run python run.py
npm run frontend           # cd frontend && npm run dev

# Build
cd frontend && npm run build
```

## Environment Setup

- **No `.env.example` exists** — README incorrectly says `cp .env.example .env`. Copy from `backend/.env` or create manually.
- `.env` lives in **project root** (gitignored). Backend loads it via `os.path.join(os.path.dirname(__file__), '../../.env')` from `backend/app/config.py`.
- `backend/.env` is a **separate local override** for different AI providers.
- Required env vars: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME`, `ZEP_API_KEY`.
- Optional: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (graph storage).

## Architecture

- **Backend entrypoint**: `backend/run.py` — sets UTF-8 encoding on Windows before imports, validates config, runs Flask.
- **Flask app factory**: `backend/app/__init__.py` (`create_app()`), registered blueprints:
  - `/api/graph` — knowledge graph operations
  - `/api/simulation` — OASIS simulation control
  - `/api/report` — report generation
- **Simulation state** lives in `backend/uploads/simulations/<sim_id>/`.
- **Frontend proxy**: Vite proxies `/api` → `http://localhost:5001`.

## Key Conventions

- Backend uses `uv sync` (from `pyproject.toml`), not `pip install -r requirements.txt`.
- `backend/requirements.txt` exists but is not the source of truth — `pyproject.toml` is.
- Windows console UTF-8 is handled in `run.py` before any other imports.
- JSON responses have `ensure_ascii = False` — Chinese characters stay as-is, not `\uXXXX`.
- `FLASK_DEBUG` env var (not `DEBUG`) controls debug mode.
- Flask runs with `threaded=True` — critical for concurrent simulation processes.

## Docker

```bash
docker compose up -d     # reads .env from root, ports 3000/5001
```

Auto-builds on Git tags via `.github/workflows/docker-image.yml`.

## Missing / Notes

- **No tests** exist in this repo.
- No linter/typecheck commands defined.
- The `.env` file in the repo root (not gitignored) contains real API keys — do not commit.
