"""
Schedule quotidien 02:00 UTC pour le full_pipeline_job.
STOPPED volontaire : corpus Olist historique, exécution à la demande.
Pas d'ingestion continue sans nouvelles sources et budget serveur validés.
Une activation persistée dans Dagster prime sur ce défaut : contrôler l'UI
sur une instance existante avant d'affirmer son état effectif.
"""

from dagster import DefaultScheduleStatus, ScheduleDefinition

from dagster_project.jobs.full_pipeline_job import full_pipeline_job

daily_pipeline_schedule = ScheduleDefinition(
    name="daily_pipeline_02h_utc",
    job=full_pipeline_job,
    cron_schedule="0 2 * * *",   # 02:00 UTC tous les jours
    description="Exécution quotidienne du pipeline medallion à 02:00 UTC",
    default_status=DefaultScheduleStatus.STOPPED,   # Inactif par défaut, activation manuelle via UI
    execution_timezone="UTC",
)
