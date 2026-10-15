from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.fields.files import FieldFile
from PIL import Image

from apps.accounts.models import User
from apps.core.management.commands import seed_demo
from apps.courses.models import Course
from apps.events.models import Event
from apps.labcompap.models import LabEquipment, LabGalleryImage
from apps.news.models import News
from apps.projects.models import Project
from apps.publications.models import Publication
from apps.researchers.models import Researcher

MODELS = (
    Group,
    User,
    Researcher,
    Project,
    News,
    Event,
    Publication,
    Course,
    LabEquipment,
    LabGalleryImage,
)


@pytest.fixture
def demo_settings(settings, tmp_path):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings) -> set[Path]:
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


@pytest.mark.django_db
def test_seed_creates_all_admin_modules_and_public_bilingual_content(demo_settings, client):
    output = StringIO()
    call_command("seed_demo", stdout=output)

    assert [model.objects.count() for model in MODELS] == [2, 2, 6, 5, 15, 8, 6, 8, 3, 3]
    assert "Seed de demonstração concluído" in output.getvalue()
    assert Researcher.objects.filter(is_active=True).count() == 5
    for user in User.objects.all():
        assert not user.is_active
        assert not user.is_staff
        assert not user.is_superuser
        assert not user.has_usable_password()
        assert user.groups.count() == 1
    for group in Group.objects.all():
        assert group.permissions.exists()
        assert not group.permissions.filter(
            content_type__app_label__in=("auth", "accounts")
        ).exists()

    files = media_files(demo_settings)
    assert len(files) == 51
    for path in files:
        with Image.open(path) as image:
            image.verify()

    for model, public_count in (
        (News, 13),
        (Project, 3),
        (Publication, 4),
        (Course, 6),
        (Event, 6),
    ):
        assert model.objects.filter(status="published").count() == public_count
        assert model.objects.filter(status="draft").count() == 1
        assert model.objects.filter(status="archived").count() == 1
        for record in model.objects.all():
            assert set(record.translations.values_list("language", flat=True)) == {"pt-br", "en"}
            record.validate_for_publication()
    for researcher in Researcher.objects.all():
        researcher.validate_for_activation()
        researcher.full_clean()

    totals = {"news": 13, "researchers": 5, "projects": 3, "publications": 4, "courses": 6}
    for language in ("pt-br", "en"):
        for route, total in totals.items():
            response = client.get(f"/api/v1/{route}", {"lang": language})
            assert response.status_code == 200, response.content
            assert response.json()["total"] == total
        page = client.get("/api/v1/news", {"lang": language, "page": 2})
        assert len(page.json()["items"]) == 1
        for period in ("upcoming", "all", "past"):
            response = client.get("/api/v1/events", {"lang": language, "period": period})
            assert response.status_code == 200, response.content
            assert response.json()["total"] > 0
        events = client.get("/api/v1/events", {"lang": language, "period": "all"}).json()
        assert "completed" in {item["schedule_status"] for item in events["items"]}
        assert {item["temporal_state"] for item in events["items"]} == {
            "upcoming",
            "ongoing",
            "past",
        }
        gallery = client.get("/api/v1/labcompap", {"lang": language}).json()
        assert len(gallery["equipment"]) == len(gallery["gallery"]) == 3

    project = Project.objects.filter(status="published").first()
    assert project.coordinator.is_active
    assert project.team.count() == 3
    assert not project.team.filter(pk=project.coordinator_id).exists()
    publication = Publication.objects.filter(status="published").first()
    detail = client.get(f"/api/v1/publications/{publication.pk}", {"lang": "pt-br"}).json()
    assert len(detail["authors"]) == 3
    assert detail["project"]["id"] == publication.project_id
    assert detail["cover"]["url"].startswith("/media/publications/covers/")


@pytest.mark.django_db
def test_seed_is_idempotent_preserves_edits_and_other_seeds(demo_settings):
    call_command("seed_labcompap")
    call_command("seed_courses")
    editorial = News.objects.create()
    call_command("seed_demo")
    assert Course.objects.count() == 12
    assert LabEquipment.objects.count() == 13
    assert LabGalleryImage.objects.count() == 12

    news = News.objects.get(translations__slug="demo-noticia-01", translations__language="pt-br")
    news.translations.filter(language="pt-br").update(title="Título editorial preservado")
    news.status = News.Status.ARCHIVED
    news.save()
    counts = [model.objects.count() for model in MODELS]
    files = media_files(demo_settings)
    original_equipment = list(
        LabEquipment.objects.exclude(inventory_code__startswith="DEMO-").values_list(
            "pk", "name_pt_br"
        )
    )

    output = StringIO()
    call_command("seed_demo", stdout=output)

    assert [model.objects.count() for model in MODELS] == counts
    assert media_files(demo_settings) == files
    assert News.objects.filter(pk=editorial.pk).exists()
    news.refresh_from_db()
    assert news.status == News.Status.ARCHIVED
    assert news.translations.get(language="pt-br").title == "Título editorial preservado"
    assert (
        list(
            LabEquipment.objects.exclude(inventory_code__startswith="DEMO-").values_list(
                "pk", "name_pt_br"
            )
        )
        == original_equipment
    )
    assert "0 criados" in output.getvalue()


@pytest.mark.django_db
def test_failed_seed_rolls_back_database_and_new_files(demo_settings, monkeypatch):
    original = seed_demo.Command._news
    demo_settings.MEDIA_ROOT.mkdir()
    existing = demo_settings.MEDIA_ROOT / "existing.txt"
    existing.write_text("Preserve este arquivo.")
    real_user = User.objects.create_user("existing@npca.example")

    def fail_after_news(self):
        original(self)
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(seed_demo.Command, "_news", fail_after_news)
    with pytest.raises(RuntimeError, match="falha simulada"):
        call_command("seed_demo")

    assert User.objects.get().pk == real_user.pk
    assert all(model.objects.count() == 0 for model in MODELS if model != User)
    assert media_files(demo_settings) == {existing}


@pytest.mark.django_db
def test_unwritable_storage_gives_actionable_error_and_rolls_back(demo_settings, monkeypatch):
    def fail_save(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(FieldFile, "save", fail_save)
    with pytest.raises(CommandError, match="MEDIA_ROOT"):
        call_command("seed_demo")

    assert all(model.objects.count() == 0 for model in MODELS)
    assert not media_files(demo_settings)


@pytest.mark.django_db
def test_seed_refuses_production_before_writing(demo_settings):
    demo_settings.DEBUG = False
    with pytest.raises(CommandError, match="desenvolvimento"):
        call_command("seed_demo")

    assert all(model.objects.count() == 0 for model in MODELS)
    assert not media_files(demo_settings)


@pytest.mark.django_db
def test_missing_image_fails_before_database_or_media_writes(demo_settings, tmp_path, monkeypatch):
    monkeypatch.setattr(seed_demo, "IMAGE_ROOT", tmp_path)
    with pytest.raises(CommandError, match="image_01.webp"):
        call_command("seed_demo")

    assert all(model.objects.count() == 0 for model in MODELS)
    assert not media_files(demo_settings)
