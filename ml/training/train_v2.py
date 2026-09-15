"""Canonical TF-IDF + numeric training entry point; candidates never auto-promote.

Reconstructed from the audit parameters; equivalence to server v19 is unverified.
Run from the repository root: python -m ml.training.train_v2
"""

import argparse
import hashlib
import json
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, fbeta_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.config import (
    LR_C,
    LR_MAX_ITER,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    NUMERIC_FEATURES,
    RANDOM_STATE,
)
from ml.training.evaluate import compute_metrics, log_artifacts
from ml.training.features import load_features, prepare_splits
from ml.training.threshold_model import ThresholdClassifier

TEXT_FEATURE = "review_comment_message"


def build_pipeline():
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    return Pipeline([
        ("features", ColumnTransformer([
            ("text", TfidfVectorizer(max_features=500, ngram_range=(1, 2), min_df=5), TEXT_FEATURE),
            ("numeric", numeric, NUMERIC_FEATURES),
        ])),
        ("clf", LogisticRegression(C=LR_C, max_iter=LR_MAX_ITER,
                                   random_state=RANDOM_STATE,
                                   class_weight="balanced", solver="liblinear")),
    ])


def select_threshold(y_validation, probability, min_precision=0.6):
    """Maximize class-0 F2 on validation, subject to a precision floor."""
    candidates = []
    for threshold in np.linspace(0.05, 0.95, 91):
        prediction = (probability >= threshold).astype(int)
        precision = precision_score(y_validation, prediction, pos_label=0, zero_division=0)
        candidates.append({"threshold": float(threshold),
                           "precision_unsatisfied": float(precision),
                           "recall_unsatisfied": float(recall_score(y_validation, prediction, pos_label=0, zero_division=0)),
                           "f2_unsatisfied": float(fbeta_score(y_validation, prediction, beta=2, pos_label=0, zero_division=0))})
    eligible = [c for c in candidates if c["precision_unsatisfied"] >= min_precision]
    if not eligible:
        raise ValueError("No validation threshold meets the precision floor; candidate rejected")
    chosen = max(eligible, key=lambda c: (c["f2_unsatisfied"], -abs(c["threshold"] - 0.5)))
    return chosen["threshold"], candidates


def metrics(model, X, y):
    result = compute_metrics(model, X, y)
    prediction = model.predict(X)
    result.update({
        "recall_unsatisfied": float(recall_score(y, prediction, pos_label=0, zero_division=0)),
        "precision_unsatisfied": float(precision_score(y, prediction, pos_label=0, zero_division=0)),
        "f2_unsatisfied": float(fbeta_score(y, prediction, beta=2, pos_label=0, zero_division=0)),
        "brier_score": float(brier_score_loss(y, model.predict_proba(X)[:, 1])),
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-label", choices=["fixtures", "production", "unverified"], default="unverified")
    parser.add_argument("--min-precision", type=float, default=0.6)
    parser.add_argument("--output", default="docs/evidence/candidate-run.json")
    args = parser.parse_args()
    if not 0 <= args.min_precision <= 1:
        parser.error("min-precision must be between 0 and 1")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    df = load_features(include_text=True)
    X_development, X_test, y_development, y_test = prepare_splits(df)
    X_train, X_validation, y_train, y_validation = train_test_split(
        X_development, y_development, test_size=0.25, stratify=y_development, random_state=RANDOM_STATE)
    if y_train.value_counts().min() < 3:
        raise ValueError("At least three training samples per class are required for calibration")
    with mlflow.start_run(run_name="tfidf-calibrated-threshold-candidate") as run:
        mlflow.set_tags({"validation_status": "pending", "data_label": args.data_label,
                         "training_data_fingerprint": hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()})
        mlflow.log_params({"solver": "liblinear", "class_weight": "balanced",
                           "tfidf_max_features": 500, "tfidf_min_df": 5,
                           "tfidf_ngram_range": "1,2", "random_state": RANDOM_STATE,
                           "calibration": "sigmoid", "calibration_cv": 3,
                           "threshold_objective": "max class-0 F2 with precision floor",
                           "min_precision_unsatisfied": args.min_precision,
                           "train_rows": len(X_train), "validation_rows": len(X_validation),
                           "test_rows": len(X_test), "split_ratio": "60/20/20"})
        baseline = build_pipeline().fit(X_train, y_train)
        calibrated = CalibratedClassifierCV(
            estimator=build_pipeline(), method="sigmoid",
            cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE))
        calibrated.fit(X_train, y_train)
        threshold, sweep = select_threshold(y_validation, calibrated.predict_proba(X_validation)[:, 1], args.min_precision)
        candidate = ThresholdClassifier(calibrated, threshold)
        mlflow.log_param("decision_threshold", threshold)
        mlflow.log_dict({"candidates": sweep}, "validation_threshold_sweep.json")
        mlflow.log_dict({"train": X_train.index.tolist(), "validation": X_validation.index.tolist(),
                         "test": X_test.index.tolist()}, "split_indices.json")
        scores = {}
         # Compare candidate variants only on validation data.
        for prefix, model in [
            ("validation_uncalibrated_05", baseline),
            ("validation_calibrated_05", calibrated),
            ("validation_tuned", candidate),
        ]:
            scores.update({
                f"{prefix}_{key}": value
                for key, value in metrics(
                    model, X_validation, y_validation
                ).items()
            })

        # The hold-out test set is evaluated only after threshold selection.
        final_test_metrics = metrics(candidate, X_test, y_test)
        scores.update({
            f"test_tuned_{key}": value
            for key, value in final_test_metrics.items()
        })
        mlflow.log_metrics(scores)
        log_artifacts(candidate, X_test, y_test)
        mlflow.sklearn.log_model(candidate, "model", input_example=X_test.iloc[:3], code_paths=["ml"])
        evidence = {"run_id": run.info.run_id, "tracking_uri": MLFLOW_TRACKING_URI,
                    "data_label": args.data_label, "threshold": threshold,
                    "validation_status": "pending", "promoted": False, "metrics": scores}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
