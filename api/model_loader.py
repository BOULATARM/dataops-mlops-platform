"""
Chargement du modele depuis le MLflow Model Registry.
/health repond meme si le modele n'est pas encore disponible (model_loaded: false).
"""

import logging
import os

import pandas as pd

from api.constants import FEATURE_ORDER

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    Charge et met en cache le modele scikit-learn depuis MLflow.
    Resilient : echec silencieux au demarrage, is_loaded=False → /predict renvoie 503.

    Méthode de prédiction : construit un pd.DataFrame avec les colonnes nommées
    dans FEATURE_ORDER. Le modèle reçoit toujours les features dans l'ordre
    d'entraînement, quelle que soit l'ordre des champs dans la requête JSON.
    """

    def __init__(self) -> None:
        self.model = None
        self.is_loaded: bool = False
        self.model_name: str | None = None
        self.model_version: str | None = None
        self.load_error: str | None = None

    def reload(self) -> None:
        """Charge (ou recharge) le modele depuis MLflow. Echec silencieux."""
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
        model_name   = os.getenv("MLFLOW_MODEL_NAME",   "SatisfactionClassifier")
        model_stage  = os.getenv("MLFLOW_MODEL_STAGE",  "Production")

        try:
            import mlflow
            import mlflow.sklearn
            mlflow.set_tracking_uri(tracking_uri)

            model_uri = f"models:/{model_name}/{model_stage}"
            logger.info("Chargement modele depuis %s", model_uri)
            self.model         = mlflow.sklearn.load_model(model_uri)
            self.is_loaded     = True
            self.model_name    = model_name
            self.model_version = model_stage
            self.load_error    = None
            logger.info("Modele '%s/%s' charge. FEATURE_ORDER=%s", model_name, model_stage, FEATURE_ORDER)

        except Exception as exc:
            self.is_loaded  = False
            self.load_error = str(exc)
            logger.warning("Modele non disponible : %s", exc)

    # Alias pour compatibilite avec les appels try_load() existants
    try_load = reload

    def _to_dataframe(self, row: dict) -> pd.DataFrame:
        """
        Construit un DataFrame 1-ligne dans l'ordre exact de FEATURE_ORDER.
        C'est le seul endroit où les valeurs sont mises en position — pas dans /predict.
        """
        return pd.DataFrame([{col: row[col] for col in FEATURE_ORDER}])

    def predict_one(self, row: dict) -> tuple[bool, float]:
        """
        Prédit pour un seul échantillon.

        Args:
            row: dict avec les clés de FEATURE_ORDER (+ éventuellement d'autres clés ignorées)

        Returns:
            (satisfied: bool, probability: float)

        Raises:
            RuntimeError si le modele n'est pas charge.
        """
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Modele non charge")

        X = self._to_dataframe(row)
        pred  = bool(self.model.predict(X)[0])
        proba = float(self.model.predict_proba(X)[0, 1])
        return pred, round(proba, 4)
