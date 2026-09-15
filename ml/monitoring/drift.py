"""Automated data-drift monitoring for the Olist satisfaction model.

Public compatibility API:
- check_drift(reference, current)
- alert_if_drift(report)
- refresh_baseline()
- run_drift_detection()

The automated path reads the current Gold feature table from DuckDB, compares it
with a persisted baseline profile, logs monitoring metrics to MLflow when
available, writes a JSON report, and can fail the Dagster asset on high drift.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import mlflow
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/duckdb/olist.duckdb")
GOLD_TABLE = os.getenv("DRIFT_GOLD_TABLE", "main_gold.gold_reviews_features")

MONITORING_DIR = Path(os.getenv("DRIFT_MONITORING_DIR", "/data/monitoring"))
BASELINE_PATH = Path(
    os.getenv("DRIFT_BASELINE_PATH", str(MONITORING_DIR / "drift_baseline.json"))
)
LATEST_REPORT_PATH = Path(
    os.getenv("DRIFT_REPORT_PATH", str(MONITORING_DIR / "drift_report_latest.json"))
)

WARNING_THRESHOLD = float(os.getenv("DRIFT_WARNING_PSI", "0.10"))
HIGH_THRESHOLD = float(os.getenv("DRIFT_HIGH_PSI", "0.20"))

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_MONITORING_EXPERIMENT_NAME", "olist-monitoring"
)


def _boolean_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "true" if default else "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


FAIL_ON_HIGH = _boolean_env("DRIFT_FAIL_ON_HIGH", False)

NUMERIC_FEATURES = [
    "delivery_delay_days",
    "review_comment_length",
    "payment_type_encoded",
]

CATEGORICAL_FEATURES = [
    "has_comment",
    "payment_type",
]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_current_data() -> pd.DataFrame:
    """Load the current Gold feature population from DuckDB."""
    connection = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        return connection.execute(f"SELECT * FROM {GOLD_TABLE}").df()
    finally:
        connection.close()


def _numeric_distribution(
    series: pd.Series,
    *,
    cutpoints: list[float] | None = None,
) -> dict[str, Any]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    values = numeric.to_numpy(dtype=float)

    if len(values) == 0:
        raise ValueError(f"No finite numeric observations for {series.name}")
    if not np.isfinite(values).all():
        raise ValueError(f"Invalid finite observations: {series.name}")

    if cutpoints is None:
        quantiles = np.quantile(values, np.linspace(0.0, 1.0, 11))
        unique = np.unique(quantiles)
        if len(unique) <= 2:
            cutpoints = []
        else:
            cutpoints = [float(value) for value in unique[1:-1]]

    edges = np.asarray([-np.inf, *cutpoints, np.inf], dtype=float)
    counts = np.histogram(values, bins=edges)[0]
    proportions = counts / counts.sum()

    return {
        "count": len(values),
        "cutpoints": [float(value) for value in cutpoints],
        "proportions": [float(value) for value in proportions],
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
    }


def _categorical_distribution(
    series: pd.Series,
    *,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    values = series.fillna("__MISSING__").astype(str)
    if values.empty:
        raise ValueError(f"No categorical observations for {series.name}")

    if categories is None:
        categories = sorted(values.unique().tolist())

    counts = values.value_counts(normalize=True)
    proportions = {
        category: float(counts.get(category, 0.0)) for category in categories
    }

    return {
        "count": len(values),
        "categories": categories,
        "proportions": proportions,
    }


def build_profile(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Build the persisted baseline distribution profile."""
    if dataframe.empty:
        raise ValueError("Current dataframe must be non-empty")

    numeric: dict[str, Any] = {}
    categorical: dict[str, Any] = {}

    for column in NUMERIC_FEATURES:
        if column in dataframe.columns:
            numeric[column] = _numeric_distribution(dataframe[column])

    for column in CATEGORICAL_FEATURES:
        if column in dataframe.columns:
            categorical[column] = _categorical_distribution(dataframe[column])

    if not numeric and not categorical:
        raise ValueError("No monitored features found in current data")

    return {
        "created_at": _utc_now(),
        "rows": len(dataframe),
        "numeric": numeric,
        "categorical": categorical,
    }


def _psi(reference: np.ndarray, current: np.ndarray) -> float:
    """Population Stability Index for aligned probability vectors."""
    if len(reference) != len(current):
        raise ValueError("PSI vectors must have the same length")

    reference = np.clip(np.asarray(reference, dtype=float), 1e-6, None)
    current = np.clip(np.asarray(current, dtype=float), 1e-6, None)
    reference = reference / reference.sum()
    current = current / current.sum()

    return float(np.sum((current - reference) * np.log(current / reference)))


def _severity(psi_value: float) -> str:
    if psi_value >= HIGH_THRESHOLD:
        return "high"
    if psi_value >= WARNING_THRESHOLD:
        return "warning"
    return "stable"


def compare_profiles(
    baseline: dict[str, Any], current_dataframe: pd.DataFrame
) -> dict[str, Any]:
    """Compare current data with a persisted baseline profile."""
    if current_dataframe.empty:
        raise ValueError("Current dataframe must be non-empty")

    features: dict[str, Any] = {}
    psi_values: list[float] = []

    for column, reference in baseline.get("numeric", {}).items():
        if column not in current_dataframe.columns:
            raise ValueError(f"Missing monitored numeric feature: {column}")

        current = _numeric_distribution(
            current_dataframe[column], cutpoints=reference["cutpoints"]
        )
        psi_value = _psi(
            np.asarray(reference["proportions"], dtype=float),
            np.asarray(current["proportions"], dtype=float),
        )
        psi_values.append(psi_value)
        features[column] = {
            "kind": "numeric",
            "psi": psi_value,
            "severity": _severity(psi_value),
            "reference_count": int(reference.get("count", 0)),
            "current_count": int(current["count"]),
        }

    for column, reference in baseline.get("categorical", {}).items():
        if column not in current_dataframe.columns:
            raise ValueError(f"Missing monitored categorical feature: {column}")

        reference_categories = list(reference["categories"])
        current_values = current_dataframe[column].fillna("__MISSING__").astype(str)
        all_categories = sorted(
            set(reference_categories) | set(current_values.unique().tolist())
        )

        reference_probabilities = np.asarray(
            [reference["proportions"].get(category, 0.0) for category in all_categories],
            dtype=float,
        )
        current_counts = current_values.value_counts(normalize=True)
        current_probabilities = np.asarray(
            [float(current_counts.get(category, 0.0)) for category in all_categories],
            dtype=float,
        )

        psi_value = _psi(reference_probabilities, current_probabilities)
        psi_values.append(psi_value)
        features[column] = {
            "kind": "categorical",
            "psi": psi_value,
            "severity": _severity(psi_value),
            "reference_count": int(reference.get("count", 0)),
            "current_count": len(current_values),
        }

    if not psi_values:
        raise ValueError("Baseline contains no monitored features")

    max_psi = float(max(psi_values))
    overall_severity = _severity(max_psi)

    return {
        "status": "checked",
        "checked_at": _utc_now(),
        "baseline_rows": int(baseline.get("rows", 0)),
        "current_rows": len(current_dataframe),
        "max_psi": max_psi,
        "warning_threshold": WARNING_THRESHOLD,
        "high_threshold": HIGH_THRESHOLD,
        "severity": overall_severity,
        "drift_detected": overall_severity == "high",
        "warning_detected": overall_severity in {"warning", "high"},
        "features": features,
    }


def alert_if_drift(report: dict[str, Any]) -> dict[str, Any]:
    """Emit explicit WARNING/ERROR logs for non-stable drift states."""
    severity = report.get("severity", "stable")

    if report.get("drift_detected") or severity == "high":
        logger.error(
            "model_drift_alert severity=%s report=%s",
            severity,
            json.dumps(report, ensure_ascii=False),
        )
    elif report.get("warning_detected") or severity != "stable":
        logger.warning(
            "model_drift_alert severity=%s report=%s",
            severity,
            json.dumps(report, ensure_ascii=False),
        )

    return report


def check_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    """Compatibility API: numeric PSI directly from two dataframes."""
    if reference.empty or current.empty:
        raise ValueError("Reference and current samples must be non-empty")

    scores: dict[str, float] = {}
    reference_numeric = reference.select_dtypes(include="number")

    for column in reference_numeric.columns:
        if column not in current.columns:
            raise ValueError(f"Missing current numeric feature: {column}")

        ref = reference[column].dropna().to_numpy(dtype=float)
        cur = pd.to_numeric(current[column], errors="coerce").dropna().to_numpy(
            dtype=float
        )

        if (
            not len(ref)
            or not len(cur)
            or not np.isfinite(ref).all()
            or not np.isfinite(cur).all()
        ):
            raise ValueError(f"Invalid finite observations: {column}")

        quantiles = np.quantile(ref, np.linspace(0.0, 1.0, 11))
        unique = np.unique(quantiles)
        internal = [] if len(unique) <= 2 else unique[1:-1].tolist()
        edges = np.asarray([-np.inf, *internal, np.inf], dtype=float)

        ref_counts = np.histogram(ref, bins=edges)[0]
        cur_counts = np.histogram(cur, bins=edges)[0]
        scores[column] = _psi(
            ref_counts / ref_counts.sum(), cur_counts / cur_counts.sum()
        )

    if not scores:
        raise ValueError("No numeric features to monitor")

    maximum = float(max(scores.values()))
    severity = _severity(maximum)
    report = {
        "checked_at": _utc_now(),
        "max_psi": maximum,
        "drift_detected": severity == "high",
        "warning_detected": severity in {"warning", "high"},
        "severity": severity,
        "psi": scores,
    }
    return alert_if_drift(report)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _save_report(report: dict[str, Any]) -> None:
    _write_json(LATEST_REPORT_PATH, report)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    history_path = LATEST_REPORT_PATH.parent / f"drift_report_{timestamp}.json"
    _write_json(history_path, report)


def _log_to_mlflow(report: dict[str, Any]) -> None:
    """Best-effort MLflow logging; drift detection still works if MLflow is down."""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

        with mlflow.start_run(run_name="data-drift-monitoring"):
            mlflow.set_tags(
                {
                    "monitoring_type": "data_drift",
                    "severity": str(report.get("severity", "unknown")),
                }
            )
            mlflow.log_params(
                {
                    "warning_threshold": WARNING_THRESHOLD,
                    "high_threshold": HIGH_THRESHOLD,
                }
            )
            mlflow.log_metrics(
                {
                    "max_psi": float(report.get("max_psi", 0.0)),
                    "drift_detected": float(
                        bool(report.get("drift_detected", False))
                    ),
                    "warning_detected": float(
                        bool(report.get("warning_detected", False))
                    ),
                    "current_rows": float(report.get("current_rows", 0)),
                }
            )
            mlflow.log_dict(report, "drift_report.json")
    except Exception:
        logger.exception("mlflow_log_error")


def refresh_baseline() -> dict[str, Any]:
    """Rebuild and persist the baseline from the current Gold table."""
    dataframe = load_current_data()
    profile = build_profile(dataframe)
    _write_json(BASELINE_PATH, profile)

    return {
        "status": "baseline_refreshed",
        "baseline_path": str(BASELINE_PATH),
        "rows": len(dataframe),
        "created_at": profile["created_at"],
    }


def run_drift_detection() -> dict[str, Any]:
    """Create the baseline when absent, otherwise compute drift."""
    current_dataframe = load_current_data()

    if not BASELINE_PATH.exists():
        baseline_result = refresh_baseline()
        report = {
            "status": "baseline_created",
            "checked_at": _utc_now(),
            "baseline_rows": baseline_result["rows"],
            "current_rows": baseline_result["rows"],
            "max_psi": 0.0,
            "severity": "stable",
            "drift_detected": False,
            "warning_detected": False,
            "features": {},
            "baseline_path": str(BASELINE_PATH),
        }
    else:
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(
                "Baseline de derive illisible : " f"{BASELINE_PATH}: {exc}"
            ) from exc

        report = compare_profiles(baseline, current_dataframe)
        report["baseline_path"] = str(BASELINE_PATH)

    alert_if_drift(report)
    _log_to_mlflow(report)
    _save_report(report)

    if report.get("drift_detected") and FAIL_ON_HIGH:
        raise RuntimeError(
            "Derive importante detectee. " f"PSI maximal={report['max_psi']}."
        )

    return report


def main() -> None:
    report = run_drift_detection()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
