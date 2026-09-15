"""
Tests de non-régression pour l'API FastAPI Olist Satisfaction.

Couvre :
- GET /health avec modèle chargé ou absent
- POST /predict sur trois cas de référence
- compatibilité des anciens payloads sans texte
- validation Pydantic
- HTTP 503 quand le modèle est absent
- ordre canonique des features V2
- métadonnées MLflow model_version + run_id
- POST /reload
- transmission de la feature texte au modèle
"""

from api.constants import FEATURE_ORDER

# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_model_loaded(self, client):
        response = client.get("/health")

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "ok"
        assert data["model_loaded"] is True
        assert data["model_name"] == "SatisfactionClassifier"
        assert data["model_version"] == "19"
        assert data["run_id"] == "source-run-19"
        assert data["load_error"] is None

    def test_health_model_absent(self, client_no_model):
        response = client_no_model.get("/health")

        # /health doit rester disponible même sans modèle.
        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "ok"
        assert data["model_loaded"] is False
        assert data["model_name"] is None
        assert data["model_version"] is None
        assert data["run_id"] is None
        assert data["load_error"] == "Test: modele absent"


# ---------------------------------------------------------------------------
# Cas de référence
# ---------------------------------------------------------------------------

# Ces payloads historiques n'envoient volontairement pas
# review_comment_message.
#
# Cela vérifie que l'API reste rétrocompatible avec les anciens clients.

CAS_SATISFAIT = {
    "delivery_delay_days": -20.0,
    "review_comment_length": 0,
    "has_comment": False,
    "payment_type_encoded": 0,
}

CAS_INSATISFAIT = {
    "delivery_delay_days": 20.0,
    "review_comment_length": 280,
    "has_comment": True,
    "payment_type_encoded": 1,
}

CAS_AMBIGU = {
    "delivery_delay_days": 3.0,
    "review_comment_length": 85,
    "has_comment": True,
    "payment_type_encoded": 0,
}


# ---------------------------------------------------------------------------
# /predict
# ---------------------------------------------------------------------------


class TestPredictCasReference:
    """
    Probabilités retournées par le MockModel défini dans tests/conftest.py.

    Ces tests vérifient la logique API sans connexion réelle à MLflow.
    """

    def test_cas_satisfait(self, client):
        response = client.post(
            "/predict",
            json=CAS_SATISFAIT,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["satisfied"] is True

        assert abs(
            data["probability"] - 0.748
        ) <= 0.01

        assert (
            data["model_name"]
            == "SatisfactionClassifier"
        )

        assert data["model_version"] == "19"
        assert data["run_id"] == "source-run-19"

    def test_cas_insatisfait(self, client):
        response = client.post(
            "/predict",
            json=CAS_INSATISFAIT,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["satisfied"] is False

        assert abs(
            data["probability"] - 0.004
        ) <= 0.01

        assert data["model_version"] == "19"
        assert data["run_id"] == "source-run-19"

    def test_cas_ambigu(self, client):
        response = client.post(
            "/predict",
            json=CAS_AMBIGU,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["satisfied"] is False

        assert abs(
            data["probability"] - 0.1754
        ) <= 0.01

    def test_probability_dans_zero_un(self, client):
        for case in [
            CAS_SATISFAIT,
            CAS_INSATISFAIT,
            CAS_AMBIGU,
        ]:
            response = client.post(
                "/predict",
                json=case,
            )

            assert response.status_code == 200

            probability = response.json()[
                "probability"
            ]

            assert 0.0 <= probability <= 1.0


# ---------------------------------------------------------------------------
# Validation Pydantic
# ---------------------------------------------------------------------------


class TestValidationPydantic:
    def test_payment_type_invalide_422(self, client):
        payload = {
            **CAS_SATISFAIT,
            "payment_type_encoded": 99,
        }

        response = client.post(
            "/predict",
            json=payload,
        )

        assert response.status_code == 422

    def test_payment_type_negatif_422(self, client):
        payload = {
            **CAS_SATISFAIT,
            "payment_type_encoded": -1,
        }

        response = client.post(
            "/predict",
            json=payload,
        )

        assert response.status_code == 422

    def test_review_length_negatif_422(self, client):
        payload = {
            **CAS_SATISFAIT,
            "review_comment_length": -5,
        }

        response = client.post(
            "/predict",
            json=payload,
        )

        assert response.status_code == 422

    def test_champ_manquant_422(self, client):
        payload = {
            "delivery_delay_days": -10.0,
        }

        response = client.post(
            "/predict",
            json=payload,
        )

        assert response.status_code == 422

    def test_has_comment_bool_valide(self, client):
        for value in [
            True,
            False,
        ]:
            payload = {
                **CAS_SATISFAIT,
                "has_comment": value,
            }

            response = client.post(
                "/predict",
                json=payload,
            )

            assert response.status_code == 200

    def test_payment_type_bornes_valides(
        self,
        client,
    ):
        for value in range(5):
            payload = {
                **CAS_SATISFAIT,
                "payment_type_encoded": value,
            }

            response = client.post(
                "/predict",
                json=payload,
            )

            assert response.status_code == 200, (
                "payment_type_encoded="
                f"{value} devrait être valide"
            )


# ---------------------------------------------------------------------------
# Modèle absent
# ---------------------------------------------------------------------------


class TestModeleAbsent:
    def test_predict_503_sans_modele(
        self,
        client_no_model,
    ):
        response = client_no_model.post(
            "/predict",
            json=CAS_SATISFAIT,
        )

        assert response.status_code == 503

        detail = response.json()["detail"]

        assert "error" in detail

    def test_health_200_meme_sans_modele(
        self,
        client_no_model,
    ):
        response = client_no_model.get(
            "/health"
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# FEATURE_ORDER
# ---------------------------------------------------------------------------


class TestFeatureOrder:
    """
    Vérifie le contrat du modèle V2 texte + numérique.
    """

    def test_feature_order_contient_toutes_les_colonnes(
        self,
    ):
        assert set(FEATURE_ORDER) == {
            "review_comment_message",
            "delivery_delay_days",
            "review_comment_length",
            "has_comment",
            "payment_type_encoded",
        }

    def test_feature_order_premier_element_est_texte(
        self,
    ):
        assert (
            FEATURE_ORDER[0]
            == "review_comment_message"
        )

    def test_ordre_json_independant(
        self,
        client,
    ):
        """
        L'ordre des champs JSON ne doit pas modifier
        le résultat de la prédiction.
        """

        ordre_standard = CAS_SATISFAIT

        ordre_inverse = {
            "payment_type_encoded": (
                CAS_SATISFAIT[
                    "payment_type_encoded"
                ]
            ),
            "has_comment": (
                CAS_SATISFAIT[
                    "has_comment"
                ]
            ),
            "review_comment_length": (
                CAS_SATISFAIT[
                    "review_comment_length"
                ]
            ),
            "delivery_delay_days": (
                CAS_SATISFAIT[
                    "delivery_delay_days"
                ]
            ),
        }

        response_standard = client.post(
            "/predict",
            json=ordre_standard,
        )

        response_inverse = client.post(
            "/predict",
            json=ordre_inverse,
        )

        assert response_standard.status_code == 200
        assert response_inverse.status_code == 200

        result_standard = (
            response_standard.json()
        )

        result_inverse = (
            response_inverse.json()
        )

        assert (
            result_standard["satisfied"]
            == result_inverse["satisfied"]
        )

        assert (
            result_standard["probability"]
            == result_inverse["probability"]
        )


# ---------------------------------------------------------------------------
# /reload
# ---------------------------------------------------------------------------


class TestReload:
    def test_reload_retourne_etat(self, client):
        response = client.post("/reload")

        assert response.status_code == 200

        data = response.json()

        assert "reloaded" in data
        assert "model_name" in data
        assert "model_version" in data
        assert "run_id" in data


# ---------------------------------------------------------------------------
# Modèle texte V2
# ---------------------------------------------------------------------------


def test_text_feature_forwarded_for_text_models():
    """
    Vérifie que ModelLoader transmet bien la feature texte
    dans le DataFrame envoyé au pipeline V2.
    """

    from api.model_loader import ModelLoader

    loader = ModelLoader()

    row = {
        **CAS_SATISFAIT,
        "review_comment_message": (
            "entrega excelente"
        ),
    }

    dataframe = loader._to_dataframe(
        row
    )

    assert (
        dataframe[
            "review_comment_message"
        ].iloc[0]
        == "entrega excelente"
    )

    assert (
        list(dataframe.columns)
        == FEATURE_ORDER
    )