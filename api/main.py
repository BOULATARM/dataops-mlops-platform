"""
FastAPI — classification satisfaction client Olist.

/health répond même sans modèle.
/predict nécessite un modèle chargé.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from api.model_loader import ModelLoader
from api.prometheus_metrics import PREDICTIONS, register_model_metrics
from api.schemas import HealthResponse, PredictRequest, PredictResponse
from api.translator import translate_french_to_portuguese

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)
predict_logger = logging.getLogger("predict_audit")

_loader = ModelLoader()
_model_metrics = register_model_metrics(_loader)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Demarrage API — chargement du modele...")
    _loader.reload()
    metrics_task = asyncio.create_task(_model_metrics.poll())
    try:
        yield
    finally:
        metrics_task.cancel()
        with suppress(asyncio.CancelledError):
            await metrics_task
        logger.info("Arret API")


app = FastAPI(
    title="Olist Satisfaction API",
    description=(
        "Classification binaire de satisfaction client Olist.\n\n"
        "**Target** : `satisfied = 1` si review_score ≥ 4, `0` sinon."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# One instrumentation per app; scrapes must not inflate API traffic.
# Metric names/labels follow prometheus-fastapi-instrumentator 7.0.0.
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=[r"^/metrics$"],
).add(metrics.requests()).add(
    metrics.latency(
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
    )
).instrument(app).expose(app, include_in_schema=False)


@app.middleware("http")
async def record_predict_latency(request, call_next):
    """Journalise la latence des appels /predict."""
    if request.url.path != "/predict":
        return await call_next(request)

    started = time.perf_counter()
    status = 500

    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            3,
        )

        predict_logger.info(
            json.dumps(
                {
                    "event": "predict_latency",
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "latency_ms": latency_ms,
                    "status_code": status,
                    "model_version": _loader.model_version,
                    "run_id": _loader.run_id,
                }
            )
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["monitoring"],
)
def health() -> HealthResponse:
    """Vérification de santé."""
    return HealthResponse(
        status="ok",
        model_loaded=_loader.is_loaded,
        model_name=_loader.model_name,
        model_version=_loader.model_version,
        run_id=_loader.run_id,
        load_error=_loader.load_error,
    )


@app.post(
    "/reload",
    tags=["monitoring"],
)
def reload_model():
    """Force le rechargement du modèle depuis MLflow."""
    _loader.reload()

    return {
        "reloaded": _loader.is_loaded,
        "model_name": _loader.model_name,
        "model_version": _loader.model_version,
        "run_id": _loader.run_id,
        "error": _loader.load_error,
    }


@app.post(
    "/predict",
    response_model=PredictResponse,
    tags=["inference"],
)
def predict(request: PredictRequest) -> PredictResponse:
    """Prédit si un client est satisfait."""
    if not _loader.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Modele non disponible",
                "hint": "POST /reload pour reessayer.",
                "load_error": _loader.load_error,
            },
        )

    original_comment = request.review_comment_message.strip()

    if original_comment:
        translated_comment = translate_french_to_portuguese(
            original_comment
        )
        review_comment_length = len(translated_comment)
        has_comment = bool(translated_comment)
    else:
        # Compatibilité avec les clients historiques qui n'envoient
        # pas encore review_comment_message.
        translated_comment = ""
        review_comment_length = request.review_comment_length
        has_comment = request.has_comment

    row = {
        "review_comment_message": translated_comment,
        "delivery_delay_days": request.delivery_delay_days,
        "review_comment_length": review_comment_length,
        "has_comment": int(has_comment),
        "payment_type_encoded": request.payment_type_encoded,
    }

    try:
        satisfied, probability = _loader.predict_one(row)
    except Exception as exc:
        logger.error(
            "Erreur prediction : %s",
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    predict_logger.info(
        (
            "ts=%s delay=%.1f len=%d comment=%s "
            "payment=%d satisfied=%s proba=%.4f"
        ),
        datetime.now(UTC).isoformat(),
        request.delivery_delay_days,
        review_comment_length,
        has_comment,
        request.payment_type_encoded,
        satisfied,
        probability,
    )

    PREDICTIONS.labels(prediction=str(int(satisfied))).inc()

    return PredictResponse(
        satisfied=satisfied,
        probability=probability,
        model_name=_loader.model_name or "",
        model_version=_loader.model_version or "",
        run_id=_loader.run_id,
    )
