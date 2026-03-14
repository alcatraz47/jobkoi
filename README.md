> [!WARNING]
> This repository is developed using vibe coding and is intended for my personal use.
> It is not developed with a multi-user focus.
> Be careful before using it in other environments, and review/harden it first.

# Jobkoi

Jobkoi is a Python 3.12 modular monolith for preparing ATS-friendly application packages from one canonical profile.

Skill and experience profiling software with deterministic Python orchestration and optional local AI assistance.

## Bootstrap scope

This repository currently includes:
- FastAPI backend with profile, job ingestion, tailoring, document, package, and profile-import APIs
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

## Optional ingestion dependencies

For improved CV extraction quality, install the optional Docling extra:

```bash
pip install -e ".[ingest]"
```

Jobkoi still runs without these extras and falls back to basic parsers.

## Profile import workflow

New ingestion features are available under **Profile Import** in the UI:
- CV import (`.pdf`, `.docx`) with source-file traceability
- Portfolio website import with same-domain crawl restrictions
- Import review decisions (approve/edit/reject) before apply
- Conflict detection and explicit resolution before apply
- Applied-fact traceability mapping after profile update

Imported data is never auto-committed to the master profile. A reviewed import run must be explicitly applied.

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

LLM readiness check (optional warm-up):

```bash
curl "http://127.0.0.1:8000/api/v1/health/llm?warmup=true"
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

## Extraction quality baseline

To score current profile-import extraction quality against golden cases:

```bash
python scripts/profile_import_quality_report.py
```

Dataset and process docs:
- `tests/quality/profile_import_goldens.json`
- `docs/extraction_quality_program.md`

## Extraction quality program

Run full extraction quality workflow locally:

```bash
python scripts/profile_import_quality_report.py
python scripts/profile_import_calibrate_confidence.py
python scripts/profile_import_quality_gate.py
```

Artifacts:
- Golden dataset: `tests/quality/profile_import_goldens.json`
- Confidence policy: `tests/quality/confidence_policy.json`
- Calibration report: `tests/quality/confidence_calibration_report.json`
- Gate thresholds: `tests/quality/quality_gate_thresholds.json`
- Program doc: `docs/extraction_quality_program.md`
