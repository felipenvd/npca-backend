import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.management.commands import seed_courses
from apps.courses.models import Course, CourseTranslation


def valid_seed_course(*, external_url: str = "https://example.com/course") -> dict:
    return {
        "course_type": "course",
        "external_url": external_url,
        "is_featured": True,
        "translations": [
            {
                "language": "pt-br",
                "title": "Curso",
                "summary": "Resumo",
                "cover_alt_text": "",
            },
            {
                "language": "en",
                "title": "Course",
                "summary": "Summary",
                "cover_alt_text": "",
            },
        ],
    }


@pytest.mark.django_db
def test_seed_creates_four_bilingual_featured_drafts_and_is_idempotent() -> None:
    output = StringIO()

    call_command("seed_courses", stdout=output)

    assert Course.objects.count() == 4
    assert CourseTranslation.objects.count() == 8
    assert Course.objects.filter(status=Course.Status.DRAFT, is_featured=True).count() == 4
    assert "4 cursos e tutoriais" in output.getvalue()
    assert list(Course.objects.values_list("external_url", flat=True)) == [
        "https://www.youtube.com/@nucleodepesquisasemcomputa1776",
        "https://www.youtube.com/playlist?list=PLN2C2-5Bqwx4GCCN9Ub7WbocW4FP9GJk8",
        "https://www.youtube.com/playlist?list=PLN2C2-5Bqwx4uaMKP0lZ5xfIWO7-rxyy-",
        "https://www.youtube.com/live/QUFYxlbVK1w",
    ]

    first = Course.objects.first()
    assert first is not None
    first.translations.filter(language="pt-br").update(title="Alteração preservada")
    call_command("seed_courses")

    assert Course.objects.count() == 4
    assert first.translations.get(language="pt-br").title == "Alteração preservada"


@pytest.mark.django_db
def test_invalid_manifest_fails_before_database_writes(tmp_path, monkeypatch) -> None:
    manifest = tmp_path / "data.json"
    manifest.write_text(json.dumps({"courses": [{"unexpected": True}]}), encoding="utf-8")
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", manifest)

    with pytest.raises(CommandError, match="não contém"):
        call_command("seed_courses")

    assert Course.objects.count() == 0
    assert CourseTranslation.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("course_type", "video", "opção válida"),
        ("external_url", "http://example.com/course", "https://"),
        ("is_featured", "true", "deve ser booleano"),
    ],
)
def test_invalid_seed_values_fail_before_database_writes(
    tmp_path,
    monkeypatch,
    field,
    value,
    message,
) -> None:
    course = valid_seed_course()
    course[field] = value
    manifest = tmp_path / "data.json"
    manifest.write_text(json.dumps({"courses": [course]}), encoding="utf-8")
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", manifest)

    with pytest.raises(CommandError, match=message):
        call_command("seed_courses")

    assert Course.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_seed_url_fails_before_database_writes(tmp_path, monkeypatch) -> None:
    course = valid_seed_course()
    manifest = tmp_path / "data.json"
    manifest.write_text(json.dumps({"courses": [course, course]}), encoding="utf-8")
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", manifest)

    with pytest.raises(CommandError, match="URL duplicada"):
        call_command("seed_courses")

    assert Course.objects.count() == 0
