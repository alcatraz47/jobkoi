# Extraction Quality Program

This document tracks production-quality extraction work for CV and portfolio imports.

## Status
- Step 1: Completed
- Step 2: Completed
- Step 3: Completed
- Step 4: Completed
- Step 5: Completed

## Step 1: Baseline and Measurement (Completed)
Deliverables:
- `app/domain/profile_import_quality.py`
- `scripts/profile_import_quality_report.py`
- `tests/quality/profile_import_goldens.json`

Run:
```bash
python scripts/profile_import_quality_report.py
```

## Step 2: Data Expansion (Completed)
Deliverables:
- Expanded golden dataset to 30+ cases (EN/DE, CV + portfolio): `tests/quality/profile_import_goldens.json`
- Dataset integrity tests: `tests/unit/test_profile_import_quality_dataset.py`

## Step 3: Parser Hardening (Completed)
Deliverables:
- Stricter role/company parsing to reduce narrative misclassification.
- Date-range extraction for experience and education lines.
- `unmapped_candidates` capture for lines that cannot be safely mapped.
- Stronger field-level confidence scoring integration.

Relevant modules:
- `app/domain/profile_import_builders.py`
- `app/domain/profile_import_types.py`
- `app/services/profile_import_service.py`

## Step 4: Confidence Calibration (Completed)
Deliverables:
- Confidence calibration runner: `scripts/profile_import_calibrate_confidence.py`
- Calibration report artifact: `tests/quality/confidence_calibration_report.json`
- Versioned policy artifact: `tests/quality/confidence_policy.json`
- Review recommendation and risk labels in API responses.

Run:
```bash
python scripts/profile_import_calibrate_confidence.py
```

## Step 5: CI Quality Gate (Completed)
Deliverables:
- Quality gate script: `scripts/profile_import_quality_gate.py`
- Threshold file: `tests/quality/quality_gate_thresholds.json`
- GitHub Actions workflow: `.github/workflows/extraction-quality.yml`

Run locally:
```bash
python scripts/profile_import_quality_gate.py
```
