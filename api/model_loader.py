"""Chargement du modèle depuis le MLflow Model Registry."""

import logging
import os

import pandas as pd

from api.constants import FEATURE_ORDER

logger = logging.getLogger(__name__)


class ModelLoader:
    """Charge et met en cache le modèle depuis MLflow."""

    def __init__(self) -> None:
        self.model = None
        self.is_loaded: bool = False
        self.model_name: str | None = None
        self.model_version: str | None = None
        self.run_id: str | None = None
        self.model_flavor: str | None = None
        self.load_error: str | None = None

    def reload(self) -> None:
        """Charge ou recharge le modèle. Un échec laisse l'API disponible."""
        tracking_uri = os.getenv(
            "MLFLOW_TRACKING_URI",
            "http://mlflow-server:5000",
        )
        model_name = os.getenv(
            "MLFLOW_MODEL_NAME",
            "SatisfactionClassifier",
        )
        model_stage = os.getenv(
            "MLFLOW_MODEL_STAGE",
            "Production",
        )

        try:
            import mlflow
            import mlflow.sklearn
            from mlflow.tracking import MlflowClient

            mlflow.set_tracking_uri(tracking_uri)

            client = MlflowClient(tracking_uri=tracking_uri)

            alias = os.getenv("MLFLOW_MODEL_ALIAS")

            if alias:
                version = client.get_model_version_by_alias(
                    model_name,
                    alias,
                )
            else:
                versions = client.get_latest_versions(
                    model_name,
                    stages=[model_stage],
                )

                if not versions:
                    raise RuntimeError(
                        f"Aucune version {model_stage} pour {model_name}"
                    )

                version = max(
                    versions,
                    key=lambda item: int(item.version),
                )

            # Charger explicitement le numéro réel et non le nom du stage.
            model_uri = f"models:/{model_name}/{version.version}"

            logger.info(
                "Chargement du modèle depuis %s",
                model_uri,
            )

            try:
                self.model = mlflow.sklearn.load_model(model_uri)
                self.model_flavor = "sklearn"
            except Exception as sklearn_error:
                logger.warning(
                    "Flavor sklearn indisponible : %s. Tentative PyFunc.",
                    sklearn_error,
                )
                self.model = mlflow.pyfunc.load_model(model_uri)
                self.model_flavor = "python_function"

            self.is_loaded = True
            self.model_name = model_name
            self.model_version = str(version.version)
            self.run_id = version.run_id
            self.load_error = None

            logger.info(
                "Modèle '%s' version=%s run_id=%s flavor=%s chargé.",
                model_name,
                self.model_version,
                self.run_id,
                self.model_flavor,
            )

        except Exception as exc:
            self.model = None
            self.is_loaded = False
            self.model_name = None
            self.model_version = None
            self.run_id = None
            self.model_flavor = None
            self.load_error = str(exc)

            logger.warning(
                "Modèle non disponible : %s",
                exc,
            )

    # Compatibilité avec les appels existants.
    try_load = reload

    def _to_dataframe(self, row: dict) -> pd.DataFrame:
        """Construit une ligne dans l'ordre canonique des features."""
        return pd.DataFrame(
            [
                {
                    column: row.get(column, "")
                    if column == "review_comment_message"
                    else row[column]
                    for column in FEATURE_ORDER
                }
            ]
        )

    def predict_one(self, row: dict) -> tuple[bool, float]:
        """Effectue une prédiction et retourne classe + probabilité."""
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Modèle non chargé")

        X = self._to_dataframe(row)

        predictions = self.model.predict(X)
        predicted_class = int(predictions[0])

        if hasattr(self.model, "predict_proba"):
            probability = float(
                self.model.predict_proba(X)[0, 1]
            )
        else:
            probability = float(predicted_class)

        return bool(predicted_class), round(probability, 4)