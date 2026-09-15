"""Canonical TF-IDF + numeric training entry point; candidates never auto-promote.

Reconstructed from the audit parameters; equivalence to server v19 is unverified.
Run from the repository root: python -m ml.training.train_v2
"""

import mlflow
import mlflow.sklearn
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
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


def main():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    df = load_features(include_text=True)
    X_train, X_test, y_train, y_test = prepare_splits(df)
    model = build_pipeline()
    with mlflow.start_run(run_name="tfidf-logreg-candidate"):
        mlflow.set_tag("validation_status", "pending")
        mlflow.log_params({"solver": "liblinear", "class_weight": "balanced",
                           "tfidf_max_features": 500, "tfidf_min_df": 5,
                           "tfidf_ngram_range": "1,2", "random_state": RANDOM_STATE})
        model.fit(X_train, y_train)
        mlflow.log_metrics(compute_metrics(model, X_test, y_test))
        log_artifacts(model, X_test, y_test)
        mlflow.sklearn.log_model(model, "model", input_example=X_test.iloc[:3])


if __name__ == "__main__":
    main()
