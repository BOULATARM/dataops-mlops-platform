"""Entraînement automatisé du modèle Olist TF-IDF."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import duckdb
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DUCKDB_PATH = os.getenv(
    "DUCKDB_PATH",
    "/data/duckdb/olist.duckdb",
)

MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlflow-server:5000",
)

MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_MLOPS_EXPERIMENT_NAME",
    "olist-satisfaction-v3",
)

MLFLOW_MODEL_NAME = os.getenv(
    "MLFLOW_MODEL_NAME",
    "SatisfactionClassifier",
)

GOLD_TABLE = "main_gold.gold_reviews_features"

TEXT_FEATURE = "review_comment_message"

NUMERIC_FEATURES = [
    "delivery_delay_days",
    "review_comment_length",
    "has_comment",
    "payment_type_encoded",
]

FEATURE_ORDER = [
    TEXT_FEATURE,
    *NUMERIC_FEATURES,
]

TARGET_COLUMN = "satisfied"

MIN_TRAINING_ROWS = int(
    os.getenv("MIN_TRAINING_ROWS", "50000")
)

MIN_ACCURACY = float(
    os.getenv("MIN_ACCURACY", "0.85")
)

MIN_RECALL_UNSATISFIED = float(
    os.getenv("MIN_RECALL_UNSATISFIED", "0.50")
)

MIN_F1_UNSATISFIED = float(
    os.getenv("MIN_F1_UNSATISFIED", "0.63")
)

TEST_SIZE = 0.20
RANDOM_STATE = 42


def _boolean_env(name: str, default: bool) -> bool:
    value = os.getenv(
        name,
        "true" if default else "false",
    )
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


AUTO_PROMOTE = _boolean_env("AUTO_PROMOTE", True)


def load_training_data() -> tuple[pd.DataFrame, str]:
    """Charge et valide le dataset Gold."""

    connection = duckdb.connect(
        DUCKDB_PATH,
        read_only=True,
    )

    try:
        df = connection.execute(
            f"""
            SELECT
                review_id,
                COALESCE(review_comment_message, '')
                    AS review_comment_message,
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
            f"Entraînement refusé : seulement {len(df):,} lignes. "
            f"Minimum requis : {MIN_TRAINING_ROWS:,}. "
            "Les fixtures de test ne doivent pas entraîner "
            "le modèle Production."
        )

    if df[TARGET_COLUMN].nunique() != 2:
        raise RuntimeError(
            "La cible satisfied doit contenir les classes 0 et 1."
        )

    df[TEXT_FEATURE] = (
        df[TEXT_FEATURE]
        .fillna("")
        .astype(str)
    )

    df["has_comment"] = (
        df["has_comment"]
        .fillna(False)
        .astype(int)
    )

    fingerprint_columns = [
        "review_id",
        *FEATURE_ORDER,
        TARGET_COLUMN,
    ]

    row_hashes = pd.util.hash_pandas_object(
        df[fingerprint_columns],
        index=False,
    )

    fingerprint = hashlib.sha256(
        row_hashes.values.tobytes()
    ).hexdigest()

    return df, fingerprint


def build_pipeline() -> Pipeline:
    """Pipeline texte TF-IDF + variables numériques."""

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "scaler",
                StandardScaler(with_mean=False),
            ),
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
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
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
                    solver="liblinear",
                ),
            ),
        ]
    )


def compute_metrics(
    model: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[dict[str, float], str]:
    """Calcule les métriques globales et par classe."""

    y_pred = model.predict(X_test)
    y_probability = model.predict_proba(X_test)[:, 1]

    precision_by_class, recall_by_class, f1_by_class, _ = (
        precision_recall_fscore_support(
            y_test,
            y_pred,
            labels=[0, 1],
            zero_division=0,
        )
    )

    metrics = {
        "accuracy": float(
            accuracy_score(y_test, y_pred)
        ),
        "f1": float(
            f1_score(y_test, y_pred)
        ),
        "precision": float(
            precision_score(
                y_test,
                y_pred,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_test,
                y_pred,
                zero_division=0,
            )
        ),
        "roc_auc": float(
            roc_auc_score(y_test, y_probability)
        ),
        "precision_unsatisfied": float(
            precision_by_class[0]
        ),
        "recall_unsatisfied": float(
            recall_by_class[0]
        ),
        "f1_unsatisfied": float(
            f1_by_class[0]
        ),
        "f1_macro": float(
            f1_score(
                y_test,
                y_pred,
                average="macro",
            )
        ),
    }

    matrix = confusion_matrix(y_test, y_pred)

    report = (
        "=== Matrice de confusion ===\n"
        f"{matrix}\n\n"
        "=== Rapport de classification ===\n"
        + classification_report(
            y_test,
            y_pred,
            target_names=[
                "insatisfait",
                "satisfait",
            ],
            zero_division=0,
        )
    )

    return metrics, report


def _find_current_model(
    client: MlflowClient,
) -> Any | None:
    """Trouve le champion, sinon la version Production."""

    try:
        return client.get_model_version_by_alias(
            MLFLOW_MODEL_NAME,
            "champion",
        )
    except Exception:
        pass

    try:
        versions = client.search_model_versions(
            f"name='{MLFLOW_MODEL_NAME}'"
        )
    except Exception:
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

    return (
        dict(run.data.metrics),
        dict(run.data.tags),
    )


def _promotion_decision(
    new_metrics: dict[str, float],
    current_metrics: dict[str, float],
) -> tuple[bool, str]:
    """Décide si la nouvelle version peut devenir champion."""

    if new_metrics["accuracy"] < MIN_ACCURACY:
        return (
            False,
            f"accuracy < {MIN_ACCURACY}",
        )

    if (
        new_metrics["recall_unsatisfied"]
        < MIN_RECALL_UNSATISFIED
    ):
        return (
            False,
            "recall classe insatisfaite insuffisant",
        )

    if (
        new_metrics["f1_unsatisfied"]
        < MIN_F1_UNSATISFIED
    ):
        return (
            False,
            "F1 classe insatisfaite insuffisant",
        )

    if not current_metrics:
        return True, "aucun modèle Production existant"

    old_f1 = current_metrics.get("f1", 0.0)

    old_recall_unsatisfied = current_metrics.get(
        "recall_unsatisfied",
        0.0,
    )

    f1_is_acceptable = (
        new_metrics["f1"] >= old_f1 - 0.002
    )

    recall_is_acceptable = (
        new_metrics["recall_unsatisfied"]
        >= old_recall_unsatisfied - 0.01
    )

    if f1_is_acceptable and recall_is_acceptable:
        return (
            True,
            "performances égales ou meilleures",
        )

    return (
        False,
        "performances inférieures au champion actuel",
    )


def train_and_register() -> dict[str, Any]:
    """Entraîne, évalue, enregistre et promeut le modèle."""

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(
        MLFLOW_EXPERIMENT_NAME
    )

    client = MlflowClient(
        tracking_uri=MLFLOW_TRACKING_URI
    )

    current_model = _find_current_model(client)

    current_metrics, current_tags = (
        _current_run_information(
            client,
            current_model,
        )
    )

    df, fingerprint = load_training_data()

    current_fingerprint = current_tags.get(
        "training_data_fingerprint"
    )

    if (
        current_model is not None
        and current_fingerprint == fingerprint
    ):
        return {
            "status": "skipped",
            "reason": "données identiques au champion actuel",
            "rows": len(df),
            "fingerprint": fingerprint,
            "promoted": False,
            "version": str(current_model.version),
            "metrics": current_metrics,
        }

    X = df[FEATURE_ORDER].copy()
    y = df[TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=y,
        )
    )

    model = build_pipeline()

    with mlflow.start_run(
        run_name="tfidf-logreg-automatic"
    ) as run:
        mlflow.log_params(
            {
                "model_type": (
                    "TF-IDF + LogisticRegression"
                ),
                "text_feature": TEXT_FEATURE,
                "numeric_features": ",".join(
                    NUMERIC_FEATURES
                ),
                "tfidf_max_features": 500,
                "tfidf_ngram_range": "1,2",
                "tfidf_min_df": 5,
                "logistic_C": 1.0,
                "logistic_solver": "liblinear",
                "test_size": TEST_SIZE,
                "random_state": RANDOM_STATE,
                "training_rows": len(X_train),
                "test_rows": len(X_test),
            }
        )

        mlflow.set_tags(
            {
                "pipeline": "dagster",
                "training_data_fingerprint": fingerprint,
                "source_table": GOLD_TABLE,
                "model_generation": "v3-tfidf",
            }
        )

        started_at = time.time()

        model.fit(X_train, y_train)

        training_seconds = (
            time.time() - started_at
        )

        metrics, report = compute_metrics(
            model,
            X_test,
            y_test,
        )

        metrics["training_seconds"] = float(
            training_seconds
        )

        mlflow.log_metrics(metrics)
        mlflow.log_text(
            report,
            "classification_report.txt",
        )

        signature = infer_signature(
            X_test.head(20),
            model.predict(X_test.head(20)),
        )

        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            signature=signature,
            input_example=X_test.head(3),
        )

        run_id = run.info.run_id

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

    promote, reason = _promotion_decision(
        metrics,
        current_metrics,
    )

    promoted = False

    if AUTO_PROMOTE and promote:
        client.transition_model_version_stage(
            name=MLFLOW_MODEL_NAME,
            version=version,
            stage="Production",
            archive_existing_versions=True,
        )

        try:
            client.set_registered_model_alias(
                name=MLFLOW_MODEL_NAME,
                alias="champion",
                version=version,
            )
        except Exception as exc:
            print(
                "Alias champion non appliqué :",
                exc,
            )

        promoted = True

    result = {
        "status": "trained",
        "run_id": run_id,
        "version": version,
        "rows": len(df),
        "fingerprint": fingerprint,
        "metrics": {
            key: round(value, 4)
            for key, value in metrics.items()
        },
        "promoted": promoted,
        "promotion_reason": reason,
    }

    return result


def main() -> None:
    result = train_and_register()

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
