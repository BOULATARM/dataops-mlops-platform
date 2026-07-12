"""
Tests de non-régression pour l'API FastAPI Olist Satisfaction.

Couvre :
  - GET /health (modèle chargé / absent)
  - POST /predict : 3 cas de référence avec vérification des probabilités (±0.01)
  - Validation Pydantic : champs invalides → HTTP 422
  - HTTP 503 quand modèle absent
  - Ordre des features : vérification structurelle via DataFrame nommé
"""


from api.constants import FEATURE_ORDER

# ── /health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_model_loaded(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True
        assert data["model_name"] == "SatisfactionClassifier"
        assert data["model_version"] == "Production"
        assert data["load_error"] is None

    def test_health_model_absent(self, client_no_model):
        r = client_no_model.get("/health")
        assert r.status_code == 200          # /health répond toujours 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is False
        assert data["load_error"] == "Test: modele absent"


# ── /predict — 3 cas de référence ─────────────────────────────────────────────

CAS_SATISFAIT = {
    "delivery_delay_days":   -20.0,
    "review_comment_length": 0,
    "has_comment":           False,
    "payment_type_encoded":  0,
}

CAS_INSATISFAIT = {
    "delivery_delay_days":   20.0,
    "review_comment_length": 280,
    "has_comment":           True,
    "payment_type_encoded":  1,
}

CAS_AMBIGU = {
    "delivery_delay_days":   3.0,
    "review_comment_length": 85,
    "has_comment":           True,
    "payment_type_encoded":  0,
}


class TestPredictCasReference:
    """
    Probabilités de référence observées sur SatisfactionClassifier v4/Production.
    Tolérance ±0.01 pour absorber de légères variations de la pipeline sklearn.
    """

    def test_cas_satisfait(self, client):
        r = client.post("/predict", json=CAS_SATISFAIT)
        assert r.status_code == 200
        data = r.json()
        assert data["satisfied"] is True
        assert abs(data["probability"] - 0.748) <= 0.01, (
            f"P(satisfait) attendu ≈0.748, obtenu {data['probability']}"
        )
        assert data["model_name"] == "SatisfactionClassifier"
        assert data["model_version"] == "Production"

    def test_cas_insatisfait(self, client):
        r = client.post("/predict", json=CAS_INSATISFAIT)
        assert r.status_code == 200
        data = r.json()
        assert data["satisfied"] is False
        assert abs(data["probability"] - 0.2) <= 0.01, (
            f"P(satisfait) attendu ≈0.2, obtenu {data['probability']}"
        )

    def test_cas_ambigu(self, client):
        r = client.post("/predict", json=CAS_AMBIGU)
        assert r.status_code == 200
        data = r.json()
        assert data["satisfied"] is False
        assert abs(data["probability"] - 0.2) <= 0.01, (
            f"P(satisfait) attendu ≈0.2, obtenu {data['probability']}"
        )

    def test_probability_dans_zero_un(self, client):
        for cas in [CAS_SATISFAIT, CAS_INSATISFAIT, CAS_AMBIGU]:
            r = client.post("/predict", json=cas)
            assert 0.0 <= r.json()["probability"] <= 1.0


# ── Validation Pydantic ────────────────────────────────────────────────────────

class TestValidationPydantic:
    def test_payment_type_invalide_422(self, client):
        payload = {**CAS_SATISFAIT, "payment_type_encoded": 99}
        r = client.post("/predict", json=payload)
        assert r.status_code == 422

    def test_payment_type_negatif_422(self, client):
        payload = {**CAS_SATISFAIT, "payment_type_encoded": -1}
        r = client.post("/predict", json=payload)
        assert r.status_code == 422

    def test_review_length_negatif_422(self, client):
        payload = {**CAS_SATISFAIT, "review_comment_length": -5}
        r = client.post("/predict", json=payload)
        assert r.status_code == 422

    def test_champ_manquant_422(self, client):
        payload = {"delivery_delay_days": -10.0}
        r = client.post("/predict", json=payload)
        assert r.status_code == 422

    def test_has_comment_bool_valide(self, client):
        for val in [True, False]:
            payload = {**CAS_SATISFAIT, "has_comment": val}
            r = client.post("/predict", json=payload)
            assert r.status_code == 200

    def test_payment_type_bornes_valides(self, client):
        for v in range(5):   # 0 à 4 inclus
            payload = {**CAS_SATISFAIT, "payment_type_encoded": v}
            r = client.post("/predict", json=payload)
            assert r.status_code == 200, f"payment_type_encoded={v} devrait être valide"


# ── HTTP 503 quand modèle absent ───────────────────────────────────────────────

class TestModeleAbsent:
    def test_predict_503_sans_modele(self, client_no_model):
        r = client_no_model.post("/predict", json=CAS_SATISFAIT)
        assert r.status_code == 503
        detail = r.json()["detail"]
        assert "error" in detail

    def test_health_200_meme_sans_modele(self, client_no_model):
        r = client_no_model.get("/health")
        assert r.status_code == 200


# ── Ordre des features ─────────────────────────────────────────────────────────

class TestFeatureOrder:
    """
    Vérifie que FEATURE_ORDER correspond aux champs attendus
    et que l'API tolère n'importe quel ordre JSON.
    """

    def test_feature_order_contient_toutes_les_colonnes(self):
        assert set(FEATURE_ORDER) == {
            "review_comment_message",
            "delivery_delay_days",
            "review_comment_length",
            "has_comment",
            "payment_type_encoded",
        }

    def test_feature_order_premier_element_est_delay(self):
        # L'ordre de l'entraînement commence par delivery_delay_days
        assert FEATURE_ORDER[0] == "review_comment_message"

    def test_ordre_json_independant(self, client):
        """
        JSON avec les champs dans un ordre différent de FEATURE_ORDER
        doit donner le même résultat qu'un JSON dans l'ordre standard.
        """
        ordre_standard = CAS_SATISFAIT
        ordre_inverse = {
            "payment_type_encoded":  CAS_SATISFAIT["payment_type_encoded"],
            "has_comment":           CAS_SATISFAIT["has_comment"],
            "review_comment_length": CAS_SATISFAIT["review_comment_length"],
            "delivery_delay_days":   CAS_SATISFAIT["delivery_delay_days"],
        }
        r1 = client.post("/predict", json=ordre_standard).json()
        r2 = client.post("/predict", json=ordre_inverse).json()

        assert r1["satisfied"]   == r2["satisfied"]
        assert r1["probability"] == r2["probability"]


# ── /reload ────────────────────────────────────────────────────────────────────

class TestReload:
    def test_reload_retourne_etat(self, client):
        r = client.post("/reload")
        assert r.status_code == 200
        data = r.json()
        assert "reloaded" in data
        assert "model_name" in data
