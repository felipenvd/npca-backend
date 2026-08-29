from django.db import migrations, models


def ensure_no_existing_researchers(apps, _schema_editor) -> None:
    researcher = apps.get_model("researchers", "Researcher")
    if researcher.objects.exists():
        raise RuntimeError(
            "Existem pesquisadores sem categoria acadêmica. "
            "Classifique-os antes de aplicar esta migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("researchers", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_no_existing_researchers, migrations.RunPython.noop),
        migrations.AddField(
            model_name="researcher",
            name="academic_category",
            field=models.CharField(
                choices=[
                    ("doctor", "Pesquisador(a) doutor(a)"),
                    ("doctoral_student", "Doutorando(a)"),
                    ("masters_student", "Mestrando(a)"),
                    (
                        "undergraduate_researcher",
                        "Graduando(a) de iniciação científica",
                    ),
                ],
                max_length=30,
                verbose_name="categoria acadêmica",
            ),
        ),
        migrations.AlterModelOptions(
            name="researcher",
            options={
                "ordering": (
                    models.Case(
                        models.When(academic_category="doctor", then=models.Value(0)),
                        models.When(
                            academic_category="doctoral_student",
                            then=models.Value(1),
                        ),
                        models.When(
                            academic_category="masters_student",
                            then=models.Value(2),
                        ),
                        models.When(
                            academic_category="undergraduate_researcher",
                            then=models.Value(3),
                        ),
                        default=models.Value(4),
                        output_field=models.IntegerField(),
                    ),
                    "display_order",
                    "full_name",
                    "pk",
                ),
                "verbose_name": "pesquisador",
                "verbose_name_plural": "pesquisadores",
            },
        ),
        migrations.AddConstraint(
            model_name="researcher",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    academic_category__in=(
                        "doctor",
                        "doctoral_student",
                        "masters_student",
                        "undergraduate_researcher",
                    )
                ),
                name="valid_researcher_academic_category",
            ),
        ),
    ]
