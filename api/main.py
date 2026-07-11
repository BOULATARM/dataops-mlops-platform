"""
FastAPI — classification satisfaction client Olist.
/health repond meme sans modele (model_loaded: false).
/predict necessite un modele charge (sinon HTTP 503).
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from api.model_loader import ModelLoader
from api.schemas import HealthResponse, PredictRequest, PredictResponse
from api.translator import translate_french_to_portuguese

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
predict_logger = logging.getLogger("predict_audit")

_loader = ModelLoader()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Demarrage API — chargement du modele...")
    _loader.reload()
    yield
    logger.info("Arret API")


app = FastAPI(
    title="Olist Satisfaction API",
    description=(
        "Classification binaire de satisfaction client Olist.\n\n"
        "**Target** : `satisfied = 1` si review_score ≥ 4, `0` sinon.\n\n"
        "**Feature order** : `delivery_delay_days, review_comment_length, "
        "has_comment, payment_type_encoded` (défini dans `api/constants.FEATURE_ORDER`)."
    ),
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["monitoring"])
def health() -> HealthResponse:
    """
    Vérification de santé.
    Répond toujours HTTP 200, même si le modèle n'est pas chargé.
    """
    return HealthResponse(
        status="ok",
        model_loaded=_loader.is_loaded,
        model_name=_loader.model_name,
        model_version=_loader.model_version,
        load_error=_loader.load_error,
    )


@app.post("/reload", tags=["monitoring"])
def reload_model():
    """Force le rechargement du modèle depuis MLflow."""
    _loader.reload()
    return {
        "reloaded":   _loader.is_loaded,
        "model_name": _loader.model_name,
        "error":      _loader.load_error,
    }


@app.post("/predict", response_model=PredictResponse, tags=["inference"])
def predict(request: PredictRequest) -> PredictResponse:
    """
    Prédit si un client est satisfait.

    Le vecteur d'entrée est construit via un DataFrame nommé dans l'ordre
    de `api/constants.FEATURE_ORDER` — indépendant de l'ordre des champs JSON.
    """
    if not _loader.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={
                "error":      "Modele non disponible",
                "hint":       "POST /reload pour reessayer.",
                "load_error": _loader.load_error,
            },
        )

    original_comment = request.review_comment_message.strip()

    translated_comment = translate_french_to_portuguese(
        original_comment
    )

    row = {
        "review_comment_message": translated_comment,
        "delivery_delay_days": request.delivery_delay_days,
        "review_comment_length": len(translated_comment),
        "has_comment": int(bool(translated_comment)),
        "payment_type_encoded": request.payment_type_encoded,
    }

    try:
        satisfied, probability = _loader.predict_one(row)
    except Exception as exc:
        logger.error("Erreur prediction : %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Audit log : timestamp + input + output (base monitoring dérive)
    predict_logger.info(
        "ts=%s delay=%.1f len=%d comment=%s payment=%d → satisfied=%s proba=%.4f",
        datetime.now(timezone.utc).isoformat(),
        request.delivery_delay_days,
        request.review_comment_length,
        request.has_comment,
        request.payment_type_encoded,
        satisfied,
        probability,
    )

    return PredictResponse(
        satisfied=satisfied,
        probability=probability,
        model_name=_loader.model_name or "",
        model_version=_loader.model_version or "",
    )
