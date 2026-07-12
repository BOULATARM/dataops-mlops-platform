"""Chargement du modèle depuis MLflow."""

import logging
import os

import pandas as pd

from api.constants import FEATURE_ORDER

logger = logging.getLogger(__name__)


class ModelLoader:
    def __init__(self) -> None:
        self.model = None
        self.is_loaded = False
        self.model_name: str | None = None
        self.model_version: str | None = None
        self.model_flavor: str | None = None
        self.load_error: str | None = None

    def reload(self) -> None:
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

            mlflow.set_tracking_uri(tracking_uri)

            model_uri = (
                f"models:/{model_name}/{model_stage}"
            )

            logger.info(
                "Chargement du modèle %s",
                model_uri,
            )

            try:
                self.model = (
                    mlflow.sklearn.load_model(
                        model_uri
                    )
                )
                self.model_flavor = "sklearn"
            except Exception as sklearn_error:
                logger.warning(
                    "Flavor sklearn indisponible : %s. "
                    "Tentative PyFunc.",
                    sklearn_error,
                )

                self.model = mlflow.pyfunc.load_model(
                    model_uri
                )
                self.model_flavor = "python_function"

            self.is_loaded = True
            self.model_name = model_name
            self.model_version = model_stage
            self.load_error = None

            logger.info(
                "Modèle chargé. Flavor=%s",
                self.model_flavor,
            )

        except Exception as exc:
            self.model = None
            self.is_loaded = False
            self.load_error = str(exc)

            logger.warning(
                "Modèle non disponible : %s",
                exc,
            )

    try_load = reload

    def _to_dataframe(
        self,
        row: dict,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    column: row[column]
                    for column in FEATURE_ORDER
                }
            ]
        )

    def predict_one(
        self,
        row: dict,
    ) -> tuple[bool, float]:
        if not self.is_loaded or self.model is None:
            raise RuntimeError(
                "Modèle non chargé"
            )

        X = self._to_dataframe(row)

        predictions = self.model.predict(X)
        predicted_class = int(predictions[0])

        if hasattr(self.model, "predict_proba"):
            probability = float(
                self.model.predict_proba(X)[0, 1]
            )
        else:
            probability = float(predicted_class)

        return (
            bool(predicted_class),
            round(probability, 4),
        )
