"""
Fixtures pytest partagées pour tests/test_api.py.

MockModel retourne des probabilités hardcodées correspondant aux valeurs
observées lors des tests manuels sur SatisfactionClassifier v4 → Production.
Il permet de tester la logique de l'API sans connexion MLflow.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app, _loader
from api.constants import FEATURE_ORDER


class MockModel:
    """
    Modèle factice reproduisant les probabilités observées sur les 3 cas de test.

    Cas référence (feature_order: delay, len, has_comment, payment) :
      satisfait   : delay=-20, len=0,   has_comment=0, payment=0 → P≈0.748
      insatisfait : delay=+20, len=280, has_comment=1, payment=1 → P≈0.004
      ambigu      : delay=+3,  len=85,  has_comment=1, payment=0 → P≈0.175
    """

    _CASES: dict[tuple, float] = {
        (-20.0, 0,   0, 0): 0.748,
        ( 20.0, 280, 1, 1): 0.004,
        (  3.0, 85,  1, 0): 0.1754,
    }

    def _proba(self, X: pd.DataFrame) -> float:
        row = X.iloc[0]
        key = (
            float(row["delivery_delay_days"]),
            int(row["review_comment_length"]),
            int(row["has_comment"]),
            int(row["payment_type_encoded"]),
        )
        if key in self._CASES:
            return self._CASES[key]
        # Fallback générique : délai négatif → plutôt satisfait
        return 0.7 if row["delivery_delay_days"] < 0 else 0.2

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        p = self._proba(X)
        return np.array([1 if p >= 0.5 else 0])

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self._proba(X)
        return np.array([[1 - p, p]])


@pytest.fixture(autouse=True)
def mock_loader():
    """Injecte le MockModel dans le loader global avant chaque test."""
    _loader.model         = MockModel()
    _loader.is_loaded     = True
    _loader.model_name    = "SatisfactionClassifier"
    _loader.model_version = "Production"
    _loader.load_error    = None
    yield
    _loader.model         = None
    _loader.is_loaded     = False
    _loader.model_name    = None
    _loader.model_version = None
    _loader.load_error    = None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def client_no_model():
    """Client avec modèle absent (is_loaded=False) pour tester /health + 503."""
    _loader.model         = None
    _loader.is_loaded     = False
    _loader.model_name    = None
    _loader.model_version = None
    _loader.load_error    = "Test: modele absent"
    return TestClient(app)
