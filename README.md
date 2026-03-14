> [!WARNING]
> This repository is developed using vibe coding and is intended for my personal use.
> It is not developed with a multi-user focus.
> Be careful before using it in other environments, and review/harden it first.

# Jobkoi

Jobkoi is a Python 3.12 modular monolith for preparing ATS-friendly application packages from one canonical profile.

Skill and experience profiling software with deterministic Python orchestration and optional local AI assistance.

## Bootstrap scope

This repository currently includes:
- FastAPI backend with profile, job ingestion, tailoring, document, and package APIs
- NiceGUI browser frontend integrated into the same application process
- Typed settings with `pydantic-settings`
- SQLAlchemy 2.0 engine and session providers

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env

docker compose up -d postgres redis
python -m app.db.init_db
uvicorn app.main:app --reload
```

Open:
- Frontend UI: `http://127.0.0.1:8000/`
- Health endpoint: `http://127.0.0.1:8000/api/v1/health`
- API docs: `http://127.0.0.1:8000/docs`

Default local DB URL (from `.env.example`):
- `postgresql+psycopg://jobkoi:jobkoi@localhost:5432/jobkoi`

## Quick start (Docker Compose)

```bash
docker compose up --build -d
```

This starts:
- `app` at `http://127.0.0.1:8000`
- `postgres` at `127.0.0.1:5432`
- `redis` at `127.0.0.1:6379`

The app container initializes database tables automatically on startup.

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Stop all services:

```bash
docker compose down
```

## DB auth troubleshooting

If you previously initialized Postgres with different credentials, the named volume may keep old users/passwords.

Reset Postgres volume and reinitialize:

```bash
docker compose down -v
docker compose up --build -d
```
