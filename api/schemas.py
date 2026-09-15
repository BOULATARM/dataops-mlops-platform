"""Schemas Pydantic pour l'API FastAPI."""

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """
    Requête compatible avec le modèle V2 texte + numérique.

    review_comment_message reste optionnel pour préserver la compatibilité
    avec les clients historiques de l'API.
    """

    review_comment_message: str = Field(
        default="",
        description="Texte du commentaire client",
    )
    delivery_delay_days: float = Field(
        description="Delai livraison en jours"
    )
    review_comment_length: int = Field(
        ge=0,
        description="Longueur du commentaire",
    )
    has_comment: bool = Field(
        description="True si commentaire present"
    )
    payment_type_encoded: int = Field(
        ge=0,
        le=4,
        description="Type de paiement encode",
    )


class PredictResponse(BaseModel):
    satisfied: bool = Field(description="True si satisfait")
    probability: float = Field(description="Probabilite satisfaction")
    model_name: str
    model_version: str
    run_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str | None
    model_version: str | None
    run_id: str | None = None
    load_error: str | None
