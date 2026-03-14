"""Enforce profile import extraction quality thresholds for CI pipelines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.profile_import_quality_report import (  # noqa: E402
    evaluate_cases,
    load_quality_cases,
    summarize_macro_f1,
)


def main() -> None:
    """Run quality gate checks and exit non-zero on failures."""

    dataset_path = Path("tests/quality/profile_import_goldens.json")
    thresholds_path = Path("tests/quality/quality_gate_thresholds.json")

    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    cases = load_quality_cases(dataset_path)
    results = evaluate_cases(cases)

    macro_f1_mean = summarize_macro_f1(results)
    cv_scores = [item.report.macro_f1 for item in results if item.source_type == "cv_document"]
    portfolio_scores = [item.report.macro_f1 for item in results if item.source_type == "portfolio_website"]

    cv_macro_mean = _mean(cv_scores)
    portfolio_macro_mean = _mean(portfolio_scores)

    failures: list[str] = []

    min_case_count = int(thresholds.get("min_case_count", 0))
    if len(results) < min_case_count:
        failures.append(f"case_count={len(results)} < min_case_count={min_case_count}")

    min_macro_f1_mean = float(thresholds.get("min_macro_f1_mean", 0.0))
    if macro_f1_mean < min_macro_f1_mean:
        failures.append(
            f"macro_f1_mean={macro_f1_mean:.4f} < min_macro_f1_mean={min_macro_f1_mean:.4f}"
        )

    min_cv_macro = float(thresholds.get("min_cv_macro_f1_mean", 0.0))
    if cv_macro_mean < min_cv_macro:
        failures.append(
            f"cv_macro_f1_mean={cv_macro_mean:.4f} < min_cv_macro_f1_mean={min_cv_macro:.4f}"
        )

    min_portfolio_macro = float(thresholds.get("min_portfolio_macro_f1_mean", 0.0))
    if portfolio_macro_mean < min_portfolio_macro:
        failures.append(
            "portfolio_macro_f1_mean="
            f"{portfolio_macro_mean:.4f} < min_portfolio_macro_f1_mean={min_portfolio_macro:.4f}"
        )

    min_case_macro = float(thresholds.get("min_case_macro_f1", 0.0))
    low_cases = [item.case_id for item in results if item.report.macro_f1 < min_case_macro]
    if low_cases:
        failures.append(
            f"{len(low_cases)} case(s) below min_case_macro_f1={min_case_macro:.4f}: "
            + ", ".join(sorted(low_cases))
        )

    output = {
        "dataset": str(dataset_path),
        "thresholds": thresholds,
        "case_count": len(results),
        "macro_f1_mean": macro_f1_mean,
        "cv_macro_f1_mean": cv_macro_mean,
        "portfolio_macro_f1_mean": portfolio_macro_mean,
        "failed": bool(failures),
        "failures": failures,
    }
    print(json.dumps(output, indent=2))

    if failures:
        raise SystemExit(1)


def _mean(values: list[float]) -> float:
    """Return rounded arithmetic mean with zero fallback."""

    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


if __name__ == "__main__":
    main()
