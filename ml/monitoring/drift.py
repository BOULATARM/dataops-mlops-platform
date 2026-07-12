"""Détection simple de dérive des données avec le PSI."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import mlflow
import numpy as np
import pandas as pd

DUCKDB_PATH = os.getenv(
    "DUCKDB_PATH",
    "/data/duckdb/olist.duckdb",
)

GOLD_TABLE = os.getenv(
    "DRIFT_GOLD_TABLE",
    "main_gold.gold_reviews_features",
)

BASELINE_PATH = Path(
    os.getenv(
        "DRIFT_BASELINE_PATH",
        "/data/duckdb/monitoring/drift_baseline.json",
    )
)

LATEST_REPORT_PATH = Path(
    os.getenv(
        "DRIFT_REPORT_PATH",
        "/data/duckdb/monitoring/latest_drift_report.json",
    )
)

HISTORY_PATH = Path(
    os.getenv(
        "DRIFT_HISTORY_PATH",
        "/data/duckdb/monitoring/drift_history.jsonl",
    )
)

MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlops_mlflow:5000",
)

MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_DRIFT_EXPERIMENT_NAME",
    "olist-drift-monitoring",
)

WARNING_THRESHOLD = float(
    os.getenv("DRIFT_WARNING_PSI", "0.10")
)

HIGH_THRESHOLD = float(
    os.getenv("DRIFT_HIGH_PSI", "0.25")
)

FAIL_ON_HIGH = os.getenv(
    "DRIFT_FAIL_ON_HIGH",
    "false",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

NUMERIC_FEATURES = [
    "delivery_delay_days",
    "review_comment_length",
]

CATEGORICAL_FEATURES = [
    "has_comment",
    "payment_type_encoded",
    "satisfied",
]

EPSILON = 1e-6


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_current_data() -> pd.DataFrame:
    """Charge la distribution actuelle depuis la table Gold."""

    connection = duckdb.connect(
        DUCKDB_PATH,
        read_only=True,
    )

    try:
        return connection.execute(
            f"""
            SELECT
                delivery_delay_days,
                review_comment_length,
                has_comment,
                payment_type_encoded,
                satisfied
            FROM {GOLD_TABLE}
            """
        ).df()
    finally:
        connection.close()


def _numeric_distribution(
    series: pd.Series,
    cutpoints: list[float] | None = None,
) -> dict[str, Any]:
    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    clean = values.dropna().to_numpy(
        dtype=float
    )

    total = int(len(values))
    null_count = int(values.isna().sum())

    if cutpoints is None:
        if clean.size:
            quantiles = np.quantile(
                clean,
                np.linspace(0.1, 0.9, 9),
            )

            cutpoints = sorted(
                {
                    float(value)
                    for value in quantiles
                }
            )
        else:
            cutpoints = []

    number_of_bins = len(cutpoints) + 1

    if clean.size:
        bin_ids = np.digitize(
            clean,
            cutpoints,
            right=True,
        )

        counts = np.bincount(
            bin_ids,
            minlength=number_of_bins,
        ).astype(float)
    else:
        counts = np.zeros(
            number_of_bins,
            dtype=float,
        )

    if total:
        proportions = (
            counts / total
        ).tolist()
    else:
        proportions = [
            0.0
        ] * number_of_bins

    # Les valeurs nulles constituent un compartiment supplémentaire.
    proportions.append(
        float(null_count / total)
        if total
        else 0.0
    )

    return {
        "cutpoints": cutpoints,
        "proportions": [
            float(value)
            for value in proportions
        ],
        "null_rate": (
            float(null_count / total)
            if total
            else 0.0
        ),
        "mean": (
            float(np.mean(clean))
            if clean.size
            else None
        ),
    }


def _categorical_distribution(
    series: pd.Series,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    normalized = (
        series.astype("string")
        .fillna("__NULL__")
        .astype(str)
    )

    total = int(len(normalized))

    if categories is None:
        categories = sorted(
            normalized.unique().tolist()
        )

    known_categories = set(categories)
    counts = normalized.value_counts(
        dropna=False
    )

    proportions = [
        float(
            counts.get(category, 0) / total
        )
        if total
        else 0.0
        for category in categories
    ]

    other_count = int(
        (
            ~normalized.isin(
                known_categories
            )
        ).sum()
    )

    proportions.append(
        float(other_count / total)
        if total
        else 0.0
    )

    return {
        "categories": categories,
        "proportions": proportions,
    }


def build_profile(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """Construit une photographie des distributions."""

    return {
        "profile_version": 1,
        "created_at": _utc_now(),
        "row_count": int(len(dataframe)),
        "numeric": {
            feature: _numeric_distribution(
                dataframe[feature]
            )
            for feature in NUMERIC_FEATURES
        },
        "categorical": {
            feature: _categorical_distribution(
                dataframe[feature]
            )
            for feature
            in CATEGORICAL_FEATURES
        },
    }


def _psi(
    expected: list[float],
    actual: list[float],
) -> float:
    expected_array = np.asarray(
        expected,
        dtype=float,
    )

    actual_array = np.asarray(
        actual,
        dtype=float,
    )

    if expected_array.shape != actual_array.shape:
        raise ValueError(
            "Les distributions PSI ont des tailles différentes."
        )

    expected_safe = np.clip(
        expected_array,
        EPSILON,
        None,
    )

    actual_safe = np.clip(
        actual_array,
        EPSILON,
        None,
    )

    return float(
        np.sum(
            (
                actual_safe
                - expected_safe
            )
            * np.log(
                actual_safe
                / expected_safe
            )
        )
    )


def _severity(
    psi_value: float,
) -> str:
    if psi_value >= HIGH_THRESHOLD:
        return "high"

    if psi_value >= WARNING_THRESHOLD:
        return "warning"

    return "stable"


def compare_profiles(
    baseline: dict[str, Any],
    current_dataframe: pd.DataFrame,
) -> dict[str, Any]:
    feature_results: dict[str, Any] = {}

    for feature in NUMERIC_FEATURES:
        baseline_profile = baseline[
            "numeric"
        ][feature]

        current_profile = (
            _numeric_distribution(
                current_dataframe[feature],
                cutpoints=baseline_profile[
                    "cutpoints"
                ],
            )
        )

        psi_value = _psi(
            baseline_profile[
                "proportions"
            ],
            current_profile[
                "proportions"
            ],
        )

        feature_results[feature] = {
            "type": "numeric",
            "psi": round(
                psi_value,
                6,
            ),
            "severity": _severity(
                psi_value
            ),
            "baseline_mean": baseline_profile[
                "mean"
            ],
            "current_mean": current_profile[
                "mean"
            ],
            "baseline_null_rate": baseline_profile[
                "null_rate"
            ],
            "current_null_rate": current_profile[
                "null_rate"
            ],
        }

    for feature in CATEGORICAL_FEATURES:
        baseline_profile = baseline[
            "categorical"
        ][feature]

        current_profile = (
            _categorical_distribution(
                current_dataframe[feature],
                categories=baseline_profile[
                    "categories"
                ],
            )
        )

        psi_value = _psi(
            baseline_profile[
                "proportions"
            ],
            current_profile[
                "proportions"
            ],
        )

        feature_results[feature] = {
            "type": "categorical",
            "psi": round(
                psi_value,
                6,
            ),
            "severity": _severity(
                psi_value
            ),
        }

    max_psi = max(
        (
            result["psi"]
            for result
            in feature_results.values()
        ),
        default=0.0,
    )

    overall_severity = _severity(
        max_psi
    )

    baseline_rows = int(
        baseline.get(
            "row_count",
            0,
        )
    )

    current_rows = int(
        len(current_dataframe)
    )

    if baseline_rows:
        row_count_change = (
            current_rows
            - baseline_rows
        ) / baseline_rows
    else:
        row_count_change = 0.0

    return {
        "status": "checked",
        "checked_at": _utc_now(),
        "baseline_created_at": baseline.get(
            "created_at"
        ),
        "baseline_rows": baseline_rows,
        "current_rows": current_rows,
        "row_count_change_ratio": round(
            float(row_count_change),
            6,
        ),
        "warning_threshold": WARNING_THRESHOLD,
        "high_threshold": HIGH_THRESHOLD,
        "max_psi": round(
            max_psi,
            6,
        ),
        "severity": overall_severity,
        "drift_detected": (
            overall_severity == "high"
        ),
        "warning_detected": (
            overall_severity
            in {
                "warning",
                "high",
            }
        ),
        "features": feature_results,
    }


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _save_report(
    report: dict[str, Any],
) -> None:
    _write_json(
        LATEST_REPORT_PATH,
        report,
    )

    HISTORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with HISTORY_PATH.open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write(
            json.dumps(
                report,
                ensure_ascii=False,
            )
            + "\n"
        )


def _log_to_mlflow(
    report: dict[str, Any],
) -> None:
    """Enregistre les métriques de dérive dans MLflow."""

    try:
        mlflow.set_tracking_uri(
            MLFLOW_TRACKING_URI
        )

        mlflow.set_experiment(
            MLFLOW_EXPERIMENT_NAME
        )

        with mlflow.start_run(
            run_name=(
                "scheduled-data-drift-check"
            )
        ):
            mlflow.log_params(
                {
                    "gold_table": GOLD_TABLE,
                    "warning_threshold": (
                        WARNING_THRESHOLD
                    ),
                    "high_threshold": (
                        HIGH_THRESHOLD
                    ),
                }
            )

            metrics: dict[str, float] = {
                "max_psi": float(
                    report.get(
                        "max_psi",
                        0.0,
                    )
                ),
                "drift_detected": float(
                    bool(
                        report.get(
                            "drift_detected",
                            False,
                        )
                    )
                ),
                "warning_detected": float(
                    bool(
                        report.get(
                            "warning_detected",
                            False,
                        )
                    )
                ),
                "current_rows": float(
                    report.get(
                        "current_rows",
                        0,
                    )
                ),
            }

            for feature, result in (
                report.get(
                    "features",
                    {},
                ).items()
            ):
                metrics[
                    f"psi_{feature}"
                ] = float(
                    result["psi"]
                )

            mlflow.log_metrics(
                metrics
            )

            mlflow.log_dict(
                report,
                "drift_report.json",
            )

    except Exception as exc:
        # Le contrôle local reste valide même si MLflow
        # est momentanément inaccessible.
        report[
            "mlflow_log_error"
        ] = str(exc)


def refresh_baseline() -> dict[str, Any]:
    """Remplace la référence par les données Gold actuelles."""

    dataframe = load_current_data()
    profile = build_profile(
        dataframe
    )

    _write_json(
        BASELINE_PATH,
        profile,
    )

    return {
        "status": "baseline_refreshed",
        "baseline_path": str(
            BASELINE_PATH
        ),
        "rows": int(
            len(dataframe)
        ),
        "created_at": profile[
            "created_at"
        ],
    }


def run_drift_detection() -> dict[str, Any]:
    """Crée la référence ou calcule la dérive."""

    current_dataframe = (
        load_current_data()
    )

    if not BASELINE_PATH.exists():
        baseline_result = (
            refresh_baseline()
        )

        report = {
            "status": "baseline_created",
            "checked_at": _utc_now(),
            "baseline_rows": (
                baseline_result["rows"]
            ),
            "current_rows": (
                baseline_result["rows"]
            ),
            "max_psi": 0.0,
            "severity": "stable",
            "drift_detected": False,
            "warning_detected": False,
            "features": {},
            "baseline_path": str(
                BASELINE_PATH
            ),
        }
    else:
        try:
            baseline = json.loads(
                BASELINE_PATH.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ) as exc:
            raise RuntimeError(
                "Baseline de dérive illisible : "
                f"{BASELINE_PATH}: {exc}"
            ) from exc

        report = compare_profiles(
            baseline,
            current_dataframe,
        )

        report["baseline_path"] = str(
            BASELINE_PATH
        )

    _log_to_mlflow(
        report
    )

    _save_report(
        report
    )

    if (
        report.get(
            "drift_detected"
        )
        and FAIL_ON_HIGH
    ):
        raise RuntimeError(
            "Dérive importante détectée. "
            f"PSI maximal={report['max_psi']}."
        )

    return report
