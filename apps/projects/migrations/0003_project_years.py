from datetime import date

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
from django.db.models.functions import ExtractYear


def dates_to_years(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.using(schema_editor.connection.alias).update(
        start_year=ExtractYear("start_date"), end_year=ExtractYear("end_date")
    )


def years_to_dates(apps, schema_editor):
    # A rollback can restore only year precision, represented as January 1.
    Project = apps.get_model("projects", "Project")
    queryset = Project.objects.using(schema_editor.connection.alias)
    for project in queryset.iterator():
        queryset.filter(pk=project.pk).update(
            start_date=date(project.start_year, 1, 1) if project.start_year else None,
            end_date=date(project.end_year, 1, 1) if project.end_year else None,
        )


class Migration(migrations.Migration):
    dependencies = [("projects", "0002_alter_projectteammember_options_and_more")]

    operations = [
        migrations.RemoveConstraint(model_name="project", name="project_end_not_before_start"),
        migrations.RemoveConstraint(model_name="project", name="published_project_has_start_date"),
        migrations.RemoveConstraint(model_name="project", name="completed_published_project_has_end"),
        migrations.AddField(
            model_name="project", name="start_year",
            field=models.PositiveSmallIntegerField(
                "ano de início", null=True, blank=True,
                validators=[MinValueValidator(1000), MaxValueValidator(9999)],
            ),
        ),
        migrations.AddField(
            model_name="project", name="end_year",
            field=models.PositiveSmallIntegerField(
                "ano de término", null=True, blank=True,
                validators=[MinValueValidator(1000), MaxValueValidator(9999)],
            ),
        ),
        migrations.RunPython(dates_to_years, years_to_dates),
        migrations.RemoveField(model_name="project", name="start_date"),
        migrations.RemoveField(model_name="project", name="end_date"),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(
                condition=models.Q(end_year__isnull=True) | models.Q(start_year__isnull=True)
                | models.Q(end_year__gte=models.F("start_year")),
                name="project_end_year_not_before_start_year",
            ),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(
                condition=~models.Q(status="published") | models.Q(start_year__isnull=False),
                name="published_project_has_start_year",
            ),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(
                condition=~models.Q(status="published", situation="completed")
                | models.Q(end_year__isnull=False),
                name="completed_published_project_has_end_year",
            ),
        ),
    ]
