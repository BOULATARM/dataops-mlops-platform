"""Canonical automated TF-IDF + numeric training for Olist satisfaction.

This module preserves the Dagster-compatible ``train_and_register`` entry point,
adds probability calibration and validation-only threshold optimisation for the
unsatisfied class, and NEVER auto-promotes a candidate to Production/champion.

A candidate may be registered as a new MLflow model version, but its
``validation_status`` remains ``pending`` until a separate manual validation and
promotion step is performed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import duckdb
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.threshold_model import ThresholdClassifier

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/duckdb/olist.duckdb")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_MLOPS_EXPERIMENT_NAME", "olist-satisfaction-v3"
)
MLFLOW_MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "SatisfactionClassifier")
GOLD_TABLE = os.getenv("ML_GOLD_TABLE", "main_gold.gold_reviews_features")

TEXT_FEATURE = "review_comment_message"
NUMERIC_FEATURES = [
    "delivery_delay_days",
    "review_comment_length",
    "has_comment",
    "payment_type_encoded",
]
FEATURE_ORDER = [TEXT_FEATURE, *NUMERIC_FEATURES]
TARGET_COLUMN = "satisfied"

MIN_TRAINING_ROWS = int(os.getenv("MIN_TRAINING_ROWS", "50000"))
MIN_ACCURACY = float(os.getenv("MIN_ACCURACY", "0.85"))
MIN_RECALL_UNSATISFIED = float(os.getenv("MIN_RECALL_UNSATISFIED", "0.50"))
MIN_F1_UNSATISFIED = float(os.getenv("MIN_F1_UNSATISFIED", "0.63"))
MIN_PRECISION_UNSATISFIED = float(
    os.getenv("MIN_PRECISION_UNSATISFIED", "0.60")
)

TEST_SIZE = 0.20
VALIDATION_SIZE_WITHIN_DEVELOPMENT = 0.25
RANDOM_STATE = 42


def load_training_data() -> tuple[pd.DataFrame, str]:
    """Load and validate the production Gold feature table."""
    connection = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        df = connection.execute(
            f"""
            SELECT
                review_id,
                COALESCE(review_comment_message, '') AS review_comment_message,
                delivery_delay_days,
                review_comment_length,
                has_comment,
                payment_type_encoded,
                satisfied
            FROM {GOLD_TABLE}
            ORDER BY review_id
            """
        ).df()
    finally:
        connection.close()

    if len(df) < MIN_TRAINING_ROWS:
        raise RuntimeError(
            "Entrainement refuse : "
            f"seulement {len(df):,} lignes. "
            f"Minimum requis : {MIN_TRAINING_ROWS:,}. "
            "Les fixtures de test ne doivent pas entrainer le modele Production."
        )

    if df[TARGET_COLUMN].nunique() != 2:
        raise RuntimeError("La cible satisfied doit contenir les classes 0 et 1.")

    df[TEXT_FEATURE] = df[TEXT_FEATURE].fillna("").astype(str)
    df["has_comment"] = df["has_comment"].fillna(False).astype(int)

    fingerprint_columns = ["review_id", *FEATURE_ORDER, TARGET_COLUMN]
    row_hashes = pd.util.hash_pandas_object(
        df[fingerprint_columns], index=False
    )
    fingerprint = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()

    return df, fingerprint


def build_pipeline() -> Pipeline:
    """TF-IDF text + numeric features + balanced logistic regression."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler(with_mean=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(
                    max_features=500,
                    ngram_range=(1, 2),
                    min_df=5,
                    lowercase=True,
                    strip_accents="unicode",
                ),
                TEXT_FEATURE,
            ),
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    max_iter=1000,
                    random_state=RANDOM_STATE,
                    class_weight="balanced",
                    solver="liblinear",
                ),
            ),
        ]
    )


def select_threshold(
    y_validation: pd.Series,
    probability: np.ndarray,
    min_precision: float = MIN_PRECISION_UNSATISFIED,
) -> tuple[float, list[dict[str, float]]]:
    """Maximise class-0 F2 on validation subject to a precision floor."""
    if not 0.0 <= min_precision <= 1.0:
        raise ValueError("min_precision must be between 0 and 1")

    candidates: list[dict[str, float]] = []

    for threshold in np.linspace(0.05, 0.95, 91):
        prediction = (probability >= threshold).astype(int)

        precision_unsatisfied = precision_score(
            y_validation,
            prediction,
            pos_label=0,
            zero_division=0,
        )
        recall_unsatisfied = recall_score(
            y_validation,
            prediction,
            pos_label=0,
            zero_division=0,
        )
        f2_unsatisfied = fbeta_score(
            y_validation,
            prediction,
            beta=2,
            pos_label=0,
            zero_division=0,
        )

        candidates.append(
            {
                "threshold": float(threshold),
                "precision_unsatisfied": float(precision_unsatisfied),
                "recall_unsatisfied": float(recall_unsatisfied),
                "f2_unsatisfied": float(f2_unsatisfied),
            }
        )

    eligible = [
        candidate
        for candidate in candidates
        if candidate["precision_unsatisfied"] >= min_precision
    ]

    if not eligible:
        raise ValueError(
            "No validation threshold meets the precision floor; candidate rejected"
        )

    chosen = max(
        eligible,
        key=lambda candidate: (
            candidate["f2_unsatisfied"],
            -abs(candidate["threshold"] - 0.5),
        ),
    )

    return chosen["threshold"], candidates


def compute_metrics(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
) -> tuple[dict[str, float], str]:
    """Compute global and unsatisfied-class metrics."""
    prediction = model.predict(X)
    probability = model.predict_proba(X)[:, 1]

    metrics: dict[str, float] = {
        "accuracy": float(accuracy_score(y, prediction)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "precision_unsatisfied": float(
            precision_score(y, prediction, pos_label=0, zero_division=0)
        ),
        "recall_unsatisfied": float(
            recall_score(y, prediction, pos_label=0, zero_division=0)
        ),
        "f1_unsatisfied": float(
            f1_score(y, prediction, pos_label=0, zero_division=0)
        ),
        "f2_unsatisfied": float(
            fbeta_score(y, prediction, beta=2, pos_label=0, zero_division=0)
        ),
        "brier_score": float(brier_score_loss(y, probability)),
    }

    if y.nunique() == 2:
        metrics["roc_auc"] = float(roc_auc_score(y, probability))
    else:
        metrics["roc_auc"] = 0.0

    matrix = confusion_matrix(y, prediction, labels=[0, 1])
    metrics.update(
        {
            "tn": float(matrix[0, 0]),
            "fp": float(matrix[0, 1]),
            "fn": float(matrix[1, 0]),
            "tp": float(matrix[1, 1]),
        }
    )

    report = classification_report(
        y,
        prediction,
        target_names=["insatisfait", "satisfait"],
        zero_division=0,
    )

    return metrics, report


def _find_current_model(client: MlflowClient) -> Any | None:
    """Find champion alias, otherwise latest Production version."""
    try:
        champion = client.get_model_version_by_alias(
            MLFLOW_MODEL_NAME,
            "champion",
        )
    except MlflowException:
        champion = None

    if champion is not None:
        return champion

    try:
        versions = client.search_model_versions(
            f"name='{MLFLOW_MODEL_NAME}'"
        )
    except MlflowException:
        return None

    production_versions = [
        version
        for version in versions
        if version.current_stage == "Production"
    ]
    if not production_versions:
        return None

    return max(
        production_versions,
        key=lambda item: int(item.version),
    )


def _current_run_information(
    client: MlflowClient,
    current_model: Any | None,
) -> tuple[dict[str, float], dict[str, str]]:
    if current_model is None or not current_model.run_id:
        return {}, {}

    run = client.get_run(current_model.run_id)
    return dict(run.data.metrics), dict(run.data.tags)


def _promotion_decision(
    new_metrics: dict[str, float],
    current_metrics: dict[str, float],
) -> tuple[bool, str]:
    """Quality gate only. This function NEVER performs promotion."""
    if new_metrics["accuracy"] < MIN_ACCURACY:
        return False, f"accuracy < {MIN_ACCURACY}"

    if new_metrics["recall_unsatisfied"] < MIN_RECALL_UNSATISFIED:
        return False, "recall classe insatisfaite insuffisant"

    if new_metrics["f1_unsatisfied"] < MIN_F1_UNSATISFIED:
        return False, "F1 classe insatisfaite insuffisant"

    if not current_metrics:
        return True, "aucun modele Production existant"

    old_f1 = current_metrics.get("f1", 0.0)
    old_recall_unsatisfied = current_metrics.get("recall_unsatisfied", 0.0)

    f1_is_acceptable = new_metrics["f1"] >= old_f1 - 0.002
    recall_is_acceptable = (
        new_metrics["recall_unsatisfied"] >= old_recall_unsatisfied - 0.01
    )

    if f1_is_acceptable and recall_is_acceptable:
        return True, "performances egales ou meilleures"

    return False, "performances inferieures au champion actuel"


def train_and_register(
    *,
    min_precision: float = MIN_PRECISION_UNSATISFIED,
    data_label: str | None = None,
) -> dict[str, Any]:
    """Train and register a pending candidate without changing Production."""
    if not 0.0 <= min_precision <= 1.0:
        raise ValueError("min_precision must be between 0 and 1")

    if data_label is None:
        data_label = os.getenv("TRAINING_DATA_LABEL", "production")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    current_model = _find_current_model(client)
    current_metrics, current_tags = _current_run_information(
        client, current_model
    )

    df, fingerprint = load_training_data()
    current_fingerprint = current_tags.get("training_data_fingerprint")

    if current_model is not None and current_fingerprint == fingerprint:
        return {
            "status": "skipped",
            "reason": "donnees identiques au champion actuel",
            "rows": len(df),
            "fingerprint": fingerprint,
            "promoted": False,
            "version": str(current_model.version),
            "metrics": current_metrics,
        }

    X = df[FEATURE_ORDER].copy()
    y = df[TARGET_COLUMN].astype(int)

    X_development, X_test, y_development, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    X_train, X_validation, y_train, y_validation = train_test_split(
        X_development,
        y_development,
        test_size=VALIDATION_SIZE_WITHIN_DEVELOPMENT,
        random_state=RANDOM_STATE,
        stratify=y_development,
    )

    if y_train.value_counts().min() < 3:
        raise RuntimeError(
            "At least three training samples per class are required for calibration"
        )

    baseline_model = build_pipeline()
    calibrated_model = CalibratedClassifierCV(
        estimator=build_pipeline(),
        method="sigmoid",
        cv=StratifiedKFold(
            n_splits=3,
            shuffle=True,
            random_state=RANDOM_STATE,
        ),
    )

    with mlflow.start_run(run_name="tfidf-calibrated-threshold-candidate") as run:
        mlflow.log_params(
            {
                "model_type": "TF-IDF + calibrated balanced LogisticRegression + threshold",
                "text_feature": TEXT_FEATURE,
                "numeric_features": ",".join(NUMERIC_FEATURES),
                "tfidf_max_features": 500,
                "tfidf_ngram_range": "1,2",
                "tfidf_min_df": 5,
                "logistic_C": 1.0,
                "logistic_solver": "liblinear",
                "class_weight": "balanced",
                "calibration": "sigmoid",
                "calibration_cv": 3,
                "threshold_objective": "max class-0 F2 with precision floor",
                "min_precision_unsatisfied": min_precision,
                "random_state": RANDOM_STATE,
                "train_rows": len(X_train),
                "validation_rows": len(X_validation),
                "test_rows": len(X_test),
                "split_ratio": "60/20/20",
            }
        )

        mlflow.set_tags(
            {
                "pipeline": "dagster",
                "training_data_fingerprint": fingerprint,
                "source_table": GOLD_TABLE,
                "model_generation": "v3-tfidf-calibrated-threshold",
                "data_label": data_label,
                "validation_status": "pending",
                "automatic_promotion": "disabled",
            }
        )

        started_at = time.time()
        baseline_model.fit(X_train, y_train)
        calibrated_model.fit(X_train, y_train)
        training_seconds = time.time() - started_at

        validation_probability = calibrated_model.predict_proba(X_validation)[:, 1]
        decision_threshold, threshold_sweep = select_threshold(
            y_validation,
            validation_probability,
            min_precision=min_precision,
        )

        candidate = ThresholdClassifier(calibrated_model, decision_threshold)

        mlflow.log_param("decision_threshold", decision_threshold)
        mlflow.log_dict(
            {"candidates": threshold_sweep},
            "validation_threshold_sweep.json",
        )
        mlflow.log_dict(
            {
                "train": X_train.index.tolist(),
                "validation": X_validation.index.tolist(),
                "test": X_test.index.tolist(),
            },
            "split_indices.json",
        )

        validation_scores: dict[str, float] = {}
        for prefix, model in [
            ("validation_uncalibrated_05", baseline_model),
            ("validation_calibrated_05", calibrated_model),
            ("validation_tuned", candidate),
        ]:
            scores, _ = compute_metrics(model, X_validation, y_validation)
            validation_scores.update(
                {f"{prefix}_{key}": value for key, value in scores.items()}
            )

        # Hold-out test is evaluated only after calibration and threshold selection.
        test_metrics, report = compute_metrics(candidate, X_test, y_test)

        metrics = {
            **validation_scores,
            **{f"test_tuned_{key}": value for key, value in test_metrics.items()},
            **test_metrics,
            "training_seconds": float(training_seconds),
        }

        mlflow.log_metrics(metrics)
        mlflow.log_text(report, "classification_report.txt")

        signature = infer_signature(
            X_test.head(20),
            candidate.predict(X_test.head(20)),
        )

        mlflow.sklearn.log_model(
            sk_model=candidate,
            artifact_path="model",
            signature=signature,
            input_example=X_test.head(3),
            code_paths=["ml"],
        )

        run_id = run.info.run_id

    # Register a NEW candidate model version. No Production/champion mutation here.
    registered_model = mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=MLFLOW_MODEL_NAME,
    )
    version = str(registered_model.version)

    client.set_model_version_tag(
        name=MLFLOW_MODEL_NAME,
        version=version,
        key="training_data_fingerprint",
        value=fingerprint,
    )
    client.set_model_version_tag(
        name=MLFLOW_MODEL_NAME,
        version=version,
        key="validation_status",
        value="pending",
    )
    client.set_model_version_tag(
        name=MLFLOW_MODEL_NAME,
        version=version,
        key="decision_threshold",
        value=str(decision_threshold),
    )

    promotion_eligible, quality_reason = _promotion_decision(
        test_metrics,
        current_metrics,
    )

    client.set_model_version_tag(
        name=MLFLOW_MODEL_NAME,
        version=version,
        key="promotion_eligible",
        value=str(promotion_eligible).lower(),
    )

    return {
        "status": "trained",
        "run_id": run_id,
        "version": version,
        "rows": len(df),
        "fingerprint": fingerprint,
        "decision_threshold": round(float(decision_threshold), 4),
        "validation_status": "pending",
        "promotion_eligible": promotion_eligible,
        "promoted": False,
        "promotion_reason": (
            "candidate registered; manual validation required; "
            "Production/champion unchanged; "
            f"quality gate: {quality_reason}"
        ),
        "metrics": {
            key: round(float(value), 4) for key, value in metrics.items()
        },
    }


def main() -> None:
    result = train_and_register()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
