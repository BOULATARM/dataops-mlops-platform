"""Assets Dagster pour le cycle MLOps."""

import json
import os
from typing import Any
from urllib.request import Request, urlopen

from dagster import (
    MetadataValue,
    Output,
    asset,
)

from dagster_project.assets.monitoring_assets import (
    data_drift_check,
)


@asset(
    group_name="ml",
    deps=[data_drift_check],
    kinds={
        "mlflow",
        "scikit-learn",
    },
    description=(
        "Entraîne le modèle TF-IDF depuis Gold, "
        "évalue ses performances et crée une version MLflow."
    ),
)
def ml_training(context):
    from ml.training.train_v2 import (
        train_and_register,
    )

    result = train_and_register()

    metadata: dict[str, MetadataValue] = {
        "status": MetadataValue.text(
            str(
                result.get(
                    "status",
                    "",
                )
            )
        ),
        "rows": MetadataValue.int(
            int(
                result.get(
                    "rows",
                    0,
                )
            )
        ),
        "version": MetadataValue.text(
            str(
                result.get(
                    "version",
                    "",
                )
            )
        ),
        "promoted": MetadataValue.text(
            str(
                result.get(
                    "promoted",
                    False,
                )
            )
        ),
        "fingerprint": MetadataValue.text(
            str(
                result.get(
                    "fingerprint",
                    "",
                )
            )[:16]
        ),
    }

    for name, value in result.get(
        "metrics",
        {},
    ).items():
        if isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            metadata[name] = (
                MetadataValue.float(
                    float(value)
                )
            )

    context.log.info(
        "Résultat entraînement : %s",
        json.dumps(
            result,
            ensure_ascii=False,
        ),
    )

    return Output(
        value=result,
        metadata=metadata,
    )


@asset(
    group_name="ml",
    kinds={
        "fastapi",
        "mlflow",
    },
    description=(
        "Recharge FastAPI lorsque le nouveau modèle "
        "a été promu dans MLflow."
    ),
)
def api_model_reload(
    context,
    ml_training: dict[str, Any],
):
    if not ml_training.get(
        "promoted",
        False,
    ):
        result = {
            "reloaded": False,
            "reason": (
                "Aucune nouvelle version promue"
            ),
        }

        return Output(
            value=result,
            metadata={
                "reloaded": MetadataValue.text(
                    "False"
                ),
                "reason": MetadataValue.text(
                    result["reason"]
                ),
            },
        )

    reload_url = os.getenv(
        "FASTAPI_RELOAD_URL",
        "http://fastapi:8000/reload",
    )

    request = Request(
        reload_url,
        data=b"",
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=60,
        ) as response:
            payload = response.read().decode(
                "utf-8"
            )
    except Exception as exc:
        raise RuntimeError(
            "Échec du rechargement FastAPI : "
            f"{exc}"
        ) from exc

    result = json.loads(
        payload
    )

    if not result.get(
        "reloaded",
        False,
    ):
        raise RuntimeError(
            "FastAPI n'a pas chargé le nouveau modèle : "
            f"{result}"
        )

    # Le nouveau modèle devient la nouvelle référence
    # des distributions de données.
    try:
        from ml.monitoring.drift import (
            refresh_baseline,
        )

        baseline_result = (
            refresh_baseline()
        )

        result[
            "drift_baseline"
        ] = baseline_result

        context.log.info(
            "Baseline de dérive mise à jour : %s",
            baseline_result,
        )
    except Exception as exc:
        context.log.warning(
            "Le modèle a été rechargé, mais la baseline "
            "de dérive n'a pas été mise à jour : %s",
            exc,
        )

        result[
            "drift_baseline_error"
        ] = str(exc)

    context.log.info(
        "FastAPI rechargée : %s",
        result,
    )

    return Output(
        value=result,
        metadata={
            "reloaded": MetadataValue.text(
                "True"
            ),
            "model_name": MetadataValue.text(
                str(
                    result.get(
                        "model_name",
                        "",
                    )
                )
            ),
        },
    )


ML_ASSETS = [
    ml_training,
    api_model_reload,
]
