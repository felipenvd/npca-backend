import json
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.fields.files import FieldFile
from PIL import Image

from apps.courses.management.commands import export_courses_seed, seed_courses
from apps.courses.models import Course, CourseTranslation


def valid_seed_course(*, external_url: str = "https://example.com/course") -> dict:
    return {
        "status": "draft",
        "display_order": 0,
        "published_at": None,
        "cover": None,
        "cover_credit": "",
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


@pytest.fixture(autouse=True)
def seed_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings):
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


@pytest.mark.django_db
def test_seed_restores_four_real_bilingual_courses_with_covers_and_is_idempotent(
    seed_media, client
) -> None:
    output = StringIO()
    source = json.loads(seed_courses.MANIFEST_PATH.read_text())["courses"]

    call_command("seed_courses", stdout=output)

    assert Course.objects.count() == 4
    assert CourseTranslation.objects.count() == 8
    assert Course.objects.filter(status=Course.Status.PUBLISHED, is_featured=True).count() == 4
    assert len(media_files(seed_media)) == 4
    assert "4 cursos e tutoriais" in output.getvalue()
    assert list(Course.objects.values_list("external_url", flat=True)) == [
        "https://www.youtube.com/@nucleodepesquisasemcomputa1776",
        "https://www.youtube.com/playlist?list=PLN2C2-5Bqwx7bdplXiGGx-4KZq__m1TXC",
        "https://www.youtube.com/playlist?list=PLN2C2-5Bqwx4GCCN9Ub7WbocW4FP9GJk8",
        "https://www.youtube.com/playlist?list=PLN2C2-5Bqwx4uaMKP0lZ5xfIWO7-rxyy-",
    ]
    for entry in source:
        course = Course.objects.get(external_url=entry["external_url"])
        assert course.display_order == entry["display_order"]
        assert course.cover_credit == entry["cover_credit"]
        assert course.published_at == datetime.fromisoformat(entry["published_at"])
        with course.cover.open("rb") as cover:
            assert (
                cover.read()
                == (seed_courses.MANIFEST_PATH.parent / "covers" / entry["cover"]).read_bytes()
            )
        with Image.open(course.cover.path) as image:
            assert image.format == "WEBP"
        for translation in entry["translations"]:
            saved = course.translations.get(language=translation["language"])
            assert saved.title == translation["title"]
            assert saved.summary == translation["summary"]
        course.validate_for_publication()
    for lang in ("pt-br", "en"):
        response = client.get("/api/v1/courses", {"lang": lang, "featured": "true"})
        assert response.status_code == 200
        assert response.json()["total"] == 4
        assert all(item["cover"]["url"].endswith(".webp") for item in response.json()["items"])

    first = Course.objects.first()
    assert first is not None
    first.translations.filter(language="pt-br").update(title="Alteração preservada")
    original_files = media_files(seed_media)
    call_command("seed_courses")

    assert Course.objects.count() == 4
    assert first.translations.get(language="pt-br").title == "Alteração preservada"
    assert media_files(seed_media) == original_files


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
        ("status", "invalid", "opção válida"),
        ("display_order", True, "deve ser inteiro"),
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
def test_missing_cover_fails_before_database_or_media_writes(tmp_path, monkeypatch, seed_media):
    course = valid_seed_course()
    course["cover"] = "missing.webp"
    manifest = tmp_path / "data.json"
    manifest.write_text(json.dumps({"courses": [course]}))
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", manifest)
    with pytest.raises(CommandError, match="Não foi possível carregar a capa"):
        call_command("seed_courses")
    assert not Course.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_storage_failure_rolls_back_records_and_new_covers(monkeypatch, seed_media):
    original = FieldFile.save
    calls = 0

    def fail_after_first(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("read-only filesystem")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FieldFile, "save", fail_after_first)
    with pytest.raises(CommandError, match="MEDIA_ROOT"):
        call_command("seed_courses")
    assert not Course.objects.exists()
    assert not CourseTranslation.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_export_round_trip_preserves_current_content_status_and_converts_covers(
    tmp_path, monkeypatch
):
    call_command("seed_courses")
    first = Course.objects.first()
    first.status = Course.Status.DRAFT
    first.is_featured = False
    first.display_order = 99
    content = BytesIO()
    Image.new("RGB", (200, 100), "red").save(content, "PNG")
    first.cover.save("cover.png", ContentFile(content.getvalue()), save=False)
    first.save()
    first.translations.filter(language="pt-br").update(title="Curso atualizado")
    root = tmp_path / "export"
    monkeypatch.setattr(export_courses_seed, "SEED_ROOT", root)

    call_command("export_courses_seed")

    records = json.loads((root / "data.json").read_text())["courses"]
    exported = next(item for item in records if item["external_url"] == first.external_url)
    assert exported["status"] == "draft"
    assert exported["display_order"] == 99
    assert exported["cover"] == "curso-atualizado.webp"
    assert all(item["cover"].endswith(".webp") for item in records)
    Course.objects.all().delete()
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", root / "data.json")
    call_command("seed_courses")

    restored = Course.objects.get(external_url=first.external_url)
    assert restored.status == Course.Status.DRAFT
    assert restored.is_featured is False
    assert restored.display_order == 99
    assert restored.published_at == first.published_at
    assert restored.translations.get(language="pt-br").title == "Curso atualizado"
    with Image.open(restored.cover.path) as image:
        assert image.format == "WEBP"
        assert image.size == (200, 100)
    assert Course.objects.count() == 4


@pytest.mark.django_db
def test_empty_export_preserves_existing_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(export_courses_seed, "SEED_ROOT", tmp_path)
    manifest = tmp_path / "data.json"
    manifest.write_text("seed existente")
    with pytest.raises(CommandError, match="Nenhum curso"):
        call_command("export_courses_seed")
    assert manifest.read_text() == "seed existente"


@pytest.mark.django_db
def test_duplicate_seed_url_fails_before_database_writes(tmp_path, monkeypatch) -> None:
    course = valid_seed_course()
    manifest = tmp_path / "data.json"
    manifest.write_text(json.dumps({"courses": [course, course]}), encoding="utf-8")
    monkeypatch.setattr(seed_courses, "MANIFEST_PATH", manifest)

    with pytest.raises(CommandError, match="URL duplicada"):
        call_command("seed_courses")

    assert Course.objects.count() == 0
