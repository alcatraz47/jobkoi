# Profile Import Quality Dataset

This folder contains golden extraction cases used to score profile-import quality.

## Files
- `profile_import_goldens.json`: baseline cases with raw source text and expected structured fields.

## Requirements
- Keep at least 30 cases.
- Cover both languages: `en`, `de`.
- Cover both source types: `cv_document`, `portfolio_website`.

## Quality process
- Add new edge cases whenever a real import run fails.
- Keep expected outputs minimal and factual.
- Do not overwrite historical failing cases; append new versions.
