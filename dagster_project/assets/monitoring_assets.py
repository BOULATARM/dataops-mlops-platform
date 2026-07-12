"""Assets Dagster pour le monitoring des données."""

import json

from dagster import (
    MetadataValue,
    Output,
    asset,
)

from dagster_project.assets.gold_assets import (
    gold_layer,
)


@asset(
    group_name="monitoring",
    deps=[gold_layer],
    kinds={
        "python",
        "mlflow",
    },
    description=(
        "Compare les distributions Gold avec une baseline "
        "et calcule le PSI de chaque feature."
    ),
)
def data_drift_check(context):
    from ml.monitoring.drift import (
        run_drift_detection,
    )

    result = run_drift_detection()

    if result.get(
        "drift_detected",
        False,
    ):
        context.log.warning(
            "Dérive importante détectée : PSI maximal=%s",
            result.get("max_psi"),
        )
    elif result.get(
        "warning_detected",
        False,
    ):
        context.log.warning(
            "Avertissement de dérive : PSI maximal=%s",
            result.get("max_psi"),
        )
    else:
        context.log.info(
            "Distributions stables : PSI maximal=%s",
            result.get("max_psi"),
        )

    return Output(
        value=result,
        metadata={
            "status": MetadataValue.text(
                str(
                    result.get(
                        "status",
                        "",
                    )
                )
            ),
            "severity": MetadataValue.text(
                str(
                    result.get(
                        "severity",
                        "",
                    )
                )
            ),
            "drift_detected": MetadataValue.text(
                str(
                    result.get(
                        "drift_detected",
                        False,
                    )
                )
            ),
            "max_psi": MetadataValue.float(
                float(
                    result.get(
                        "max_psi",
                        0.0,
                    )
                )
            ),
            "current_rows": MetadataValue.int(
                int(
                    result.get(
                        "current_rows",
                        result.get(
                            "baseline_rows",
                            0,
                        ),
                    )
                )
            ),
            "feature_psi": MetadataValue.text(
                json.dumps(
                    {
                        name: values.get(
                            "psi"
                        )
                        for name, values
                        in result.get(
                            "features",
                            {},
                        ).items()
                    },
                    ensure_ascii=False,
                )
            ),
        },
    )


MONITORING_ASSETS = [
    data_drift_check,
]
