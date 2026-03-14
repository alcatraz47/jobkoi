# Jobkoi

Jobkoi is a Python 3.12 modular monolith for preparing ATS-friendly application packages from one canonical profile.

## Bootstrap scope

This repository currently includes:
- FastAPI app bootstrap with lifespan
- Typed settings with `pydantic-settings`
- SQLAlchemy 2.0 engine and session providers
- Health endpoint

Business modules (profile, analysis, tailoring, documents) are intentionally not implemented yet.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```
