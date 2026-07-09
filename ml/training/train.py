"""
Entraînement : features numériques → LogisticRegression.
Tracking MLflow + enregistrement du modèle dans le Registry (stage Production).

gold_reviews_features contient 4 features dérivées (pas le texte brut), ce qui
est cohérent avec l'API /predict qui reçoit ces mêmes 4 valeurs numériques.

Exécution locale (depuis la racine du projet) :
    python -m ml.training.train

Variables d'environnement (optionnelles) :
    MLFLOW_TRACKING_URI   http://localhost:5100  (défaut)
    DUCKDB_PATH           chemin vers olist.duckdb
"""
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.training.config import (
    LR_C,
    LR_MAX_ITER,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_MODEL_NAME,
    MLFLOW_TRACKING_URI,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TEST_SIZE,
)
from ml.training.evaluate import compute_metrics, log_artifacts
from ml.training.features import load_features, prepare_splits


def build_pipeline() -> Pipeline:
    """
    Pipeline :
      - SimpleImputer(median) pour delivery_delay_days nullable
      - StandardScaler
      - LogisticRegression binaire (class_weight=balanced pour compenser le déséquilibre)
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            C=LR_C,
            max_iter=LR_MAX_ITER,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            solver="lbfgs",
        )),
    ])


def _promote_to_production(model_name: str) -> None:
    """Passe la dernière version du modèle (stage=None) en Production."""
    client = MlflowClient()
    versions = client.get_latest_versions(model_name, stages=["None"])
    if not versions:
        print(f"[WARN] Aucune version en stage None trouvee pour '{model_name}'")
        return
    v = versions[0].version
    client.transition_model_version_stage(
        name=model_name,
        version=v,
        stage="Production",
        archive_existing_versions=True,
    )
    print(f"Modele '{model_name}' v{v} → Production")


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    print(f"MLflow tracking : {MLFLOW_TRACKING_URI}")

    df = load_features()
    X_train, X_test, y_train, y_test = prepare_splits(df)

    pipeline = build_pipeline()

    with mlflow.start_run(run_name="logreg-numeric-v1") as run:
        mlflow.log_params({
            "model_type":      "LogisticRegression",
            "feature_order":   ",".join(NUMERIC_FEATURES),
            "lr_C":            LR_C,
            "lr_max_iter":     LR_MAX_ITER,
            "lr_class_weight": "balanced",
            "lr_solver":       "lbfgs",
            "imputer":         "median",
            "scaler":          "StandardScaler",
            "test_size":       TEST_SIZE,
            "train_rows":      len(X_train),
            "test_rows":       len(X_test),
            "random_state":    RANDOM_STATE,
        })

        print("Entraînement en cours...")
        pipeline.fit(X_train, y_train)

        metrics = compute_metrics(pipeline, X_test, y_test)
        mlflow.log_metrics(metrics)
        log_artifacts(pipeline, X_test, y_test)

        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            registered_model_name=MLFLOW_MODEL_NAME,
            input_example=X_test.iloc[:3],
        )

        print(f"\nRun ID : {run.info.run_id}")
        print("Metriques :")
        for k, v in metrics.items():
            print(f"  {k:10s} = {v:.4f}")

    _promote_to_production(MLFLOW_MODEL_NAME)
    print("\nEntraînement termine. Modele enregistre dans le Registry MLflow.")


if __name__ == "__main__":
    main()
