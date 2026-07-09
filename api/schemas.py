"""Schemas Pydantic pour l'API FastAPI."""

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """
    Champs NOMMÉS — ordre indépendant, aucun risque de permutation positionnelle.
    Correspondent exactement à api/constants.FEATURE_ORDER.
    """
    delivery_delay_days:   float = Field(
        description="Délai livraison réelle vs estimée en jours (négatif = en avance, positif = en retard)"
    )
    review_comment_length: int   = Field(
        ge=0,
        description="Nombre de caractères du commentaire (0 si aucun commentaire)"
    )
    has_comment:           bool  = Field(
        description="True si le client a écrit un commentaire"
    )
    payment_type_encoded:  int   = Field(
        ge=0, le=4,
        description="Type de paiement encodé : 0=credit_card, 1=boleto, 2=voucher, 3=debit_card, 4=autre"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Client satisfait",
                    "value": {
                        "delivery_delay_days": -20.0,
                        "review_comment_length": 0,
                        "has_comment": False,
                        "payment_type_encoded": 0,
                    }
                },
                {
                    "summary": "Client insatisfait",
                    "value": {
                        "delivery_delay_days": 15.0,
                        "review_comment_length": 250,
                        "has_comment": True,
                        "payment_type_encoded": 1,
                    }
                },
            ]
        }
    }


class PredictResponse(BaseModel):
    satisfied:     bool  = Field(description="True si le client est prédit satisfait (score >= 4)")
    probability:   float = Field(description="Probabilité d'être satisfait (classe 1), entre 0 et 1")
    model_name:    str
    model_version: str


class HealthResponse(BaseModel):
    status:        str
    model_loaded:  bool
    model_name:    str | None
    model_version: str | None
    load_error:    str | None
