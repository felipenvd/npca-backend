from datetime import date

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_date_migration_preserves_years_nulls_and_publication_status():
    before = ("projects", "0002_alter_projectteammember_options_and_more")
    after = ("projects", "0003_project_years")
    executor = MigrationExecutor(connection)
    executor.migrate([before])
    old_apps = executor.loader.project_state([before]).apps
    Researcher = old_apps.get_model("researchers", "Researcher")
    Project = old_apps.get_model("projects", "Project")
    coordinator = Researcher.objects.create(full_name="Coordenação", academic_category="doctor")
    samples = [
        (None, None, "draft", "ongoing"),
        (date(2024, 2, 29), None, "published", "ongoing"),
        (date(2022, 6, 15), date(2023, 12, 31), "published", "completed"),
        (date(2025, 1, 31), date(2025, 2, 1), "draft", "completed"),
    ]
    try:
        records = [
            Project.objects.create(
                coordinator=coordinator,
                start_date=start,
                end_date=end,
                status=status,
                situation=situation,
            )
            for start, end, status, situation in samples
        ]
        executor = MigrationExecutor(connection)
        executor.migrate([after])
        NewProject = executor.loader.project_state([after]).apps.get_model("projects", "Project")
        for original, (start, end, status, situation) in zip(records, samples, strict=True):
            migrated = NewProject.objects.get(pk=original.pk)
            assert migrated.start_year == (start.year if start else None)
            assert migrated.end_year == (end.year if end else None)
            assert migrated.status == status
            assert migrated.situation == situation
            assert migrated.coordinator_id == coordinator.pk

        executor = MigrationExecutor(connection)
        executor.migrate([before])
        ReversedProject = executor.loader.project_state([before]).apps.get_model(
            "projects", "Project"
        )
        for original, (start, end, _status, _situation) in zip(records, samples, strict=True):
            reversed_record = ReversedProject.objects.get(pk=original.pk)
            assert reversed_record.start_date == (date(start.year, 1, 1) if start else None)
            assert reversed_record.end_date == (date(end.year, 1, 1) if end else None)
    finally:
        MigrationExecutor(connection).migrate([after])
