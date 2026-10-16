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

from apps.projects.management.commands import export_projects_seed, seed_projects
from apps.projects.models import Project, ProjectTeamMember, ProjectTranslation
from apps.researchers.models import Researcher


@pytest.fixture(autouse=True)
def seed_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings):
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


def seed_records():
    return json.loads((seed_projects.SEED_ROOT / "data.json").read_text())["projects"]


def create_researchers():
    names = set()
    for entry in seed_records():
        if entry["coordinator"]:
            names.add(entry["coordinator"])
        names.update(member["researcher"] for member in entry["team"] if member["researcher"])
    for name in sorted(names):
        Researcher.objects.create(
            full_name=name, academic_category=Researcher.AcademicCategory.DOCTOR
        )


def write_seed(tmp_path, monkeypatch, records):
    (tmp_path / "data.json").write_text(json.dumps({"projects": records}), encoding="utf-8")
    monkeypatch.setattr(seed_projects, "SEED_ROOT", tmp_path)


@pytest.mark.django_db
def test_real_seed_restores_projects_years_translations_and_ordered_teams(client, seed_media):
    source = seed_records()
    Researcher.objects.create(
        full_name="Cadastro que desloca os IDs",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    create_researchers()

    call_command("seed_projects")

    assert Project.objects.count() == 4
    assert ProjectTranslation.objects.count() == 8
    assert ProjectTeamMember.objects.count() == 54
    assert ProjectTeamMember.objects.filter(researcher__isnull=False).count() == 12
    assert not media_files(seed_media)
    for entry in source:
        project = Project.objects.get(display_order=entry["display_order"])
        for field in seed_projects.MODEL_FIELDS:
            expected = entry[field]
            if field == "published_at" and expected:
                expected = datetime.fromisoformat(expected)
            assert getattr(project, field) == expected
        assert project.coordinator.full_name == entry["coordinator"]
        for translation in entry["translations"]:
            saved = project.translations.get(language=translation["language"])
            assert all(getattr(saved, field) == value for field, value in translation.items())
        assert [
            {
                "researcher": member.researcher.full_name if member.researcher else None,
                "external_name": member.external_name,
            }
            for member in project.team_memberships.select_related("researcher")
        ] == entry["team"]
        project.validate_for_publication()
    for language in ("pt-br", "en"):
        response = client.get("/api/v1/projects", {"lang": language, "featured": "true"})
        assert response.status_code == 200
        assert response.json()["total"] == 4
        expected = [
            next(t for t in entry["translations"] if t["language"] == language)
            for entry in sorted(source, key=lambda item: item["display_order"])
        ]
        assert [item["slug"] for item in response.json()["items"]] == [
            entry["slug"] for entry in expected
        ]
        for item in response.json()["items"]:
            detail = client.get(f"/api/v1/projects/{item['slug']}", {"lang": language})
            assert detail.status_code == 200
            assert detail.json()["team"]

    project = Project.objects.first()
    project.is_featured = False
    project.save()
    project.translations.filter(language="pt-br").update(title="Edição preservada")
    output = StringIO()
    call_command("seed_projects", stdout=output)
    assert "0 criados; 4 existentes preservados" in output.getvalue()
    assert Project.objects.count() == 4
    project.refresh_from_db()
    assert not project.is_featured
    assert project.translations.get(language="pt-br").title == "Edição preservada"


@pytest.mark.django_db
def test_partial_seed_preserves_existing_project_and_creates_missing_ones():
    create_researchers()
    entry = seed_records()[0]["translations"][0]
    project = Project.objects.create(funding="Edição manual")
    ProjectTranslation.objects.create(project=project, **entry)
    call_command("seed_projects")
    project.refresh_from_db()
    assert project.status == Project.Status.DRAFT
    assert project.funding == "Edição manual"
    assert project.coordinator is None
    assert not project.team_memberships.exists()
    assert Project.objects.count() == 4


@pytest.mark.django_db
@pytest.mark.parametrize("ambiguous", [False, True])
def test_missing_or_ambiguous_researcher_prevents_all_writes(ambiguous, seed_media):
    if ambiguous:
        create_researchers()
        Researcher.objects.create(
            full_name=seed_records()[0]["coordinator"],
            academic_category=Researcher.AcademicCategory.DOCTOR,
        )
    with pytest.raises(CommandError, match="Execute seed_researchers"):
        call_command("seed_projects")
    assert not Project.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "invalid", "opção inválida"),
        ("start_year", True, "deve ser inteiro"),
        ("start_year", 999, "1000"),
        ("end_year", 2020, "posterior"),
        ("display_order", -1, "0"),
        ("is_featured", "true", "booleano"),
        ("cover", "missing.webp", "Não foi possível carregar a capa"),
        ("cover", "../outside.webp", "somente o nome"),
        ("translations", [], "tradução"),
    ],
)
def test_invalid_seed_fails_before_writes(tmp_path, monkeypatch, field, value, message):
    records = seed_records()
    records[0][field] = value
    write_seed(tmp_path, monkeypatch, records)
    with pytest.raises(CommandError, match=message):
        call_command("seed_projects")
    assert not Project.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("invalid", ["slug", "identity", "coordinator", "end_year"])
def test_invalid_relationships_or_completed_period_fail_before_writes(
    tmp_path, monkeypatch, invalid
):
    create_researchers()
    records = seed_records()
    if invalid == "slug":
        records[1]["translations"][0]["slug"] = records[0]["translations"][0]["slug"]
        message = "Slug duplicado"
    elif invalid == "identity":
        records[0]["team"][0] = {"researcher": records[0]["coordinator"], "external_name": "Nome"}
        message = "somente uma identidade"
    elif invalid == "coordinator":
        records[0]["team"][0] = {"researcher": records[0]["coordinator"], "external_name": ""}
        message = "duplicado"
    else:
        records[0]["situation"] = "completed"
        message = "ano de término"
    write_seed(tmp_path, monkeypatch, records)
    with pytest.raises(CommandError, match=message):
        call_command("seed_projects")
    assert not Project.objects.exists()


@pytest.mark.django_db
def test_storage_failure_rolls_back_projects_teams_translations_and_covers(
    tmp_path, monkeypatch, seed_media
):
    create_researchers()
    records = seed_records()
    covers = tmp_path / "covers"
    covers.mkdir()
    Image.new("RGB", (100, 100), "white").save(covers / "cover.webp", "WEBP")
    for entry in records:
        entry["cover"] = "cover.webp"
    write_seed(tmp_path, monkeypatch, records)
    original = FieldFile.save
    calls = 0

    def fail_on_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Storage indisponível")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FieldFile, "save", fail_on_second)
    with pytest.raises(CommandError, match="MEDIA_ROOT"):
        call_command("seed_projects")
    assert not Project.objects.exists()
    assert not ProjectTranslation.objects.exists()
    assert not ProjectTeamMember.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_export_round_trip_preserves_draft_links_metadata_and_converts_cover(tmp_path, monkeypatch):
    create_researchers()
    call_command("seed_projects")
    project = Project.objects.first()
    project.status = Project.Status.DRAFT
    project.is_featured = False
    project.end_year = project.start_year + 1
    project.website_url = "https://example.org/project"
    image = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image, "PNG")
    project.cover.save("new-cover.png", ContentFile(image.getvalue()), save=False)
    project.save()
    project.translations.filter(language="pt-br").update(seo_title="SEO preservado")
    root = tmp_path / "export"
    monkeypatch.setattr(export_projects_seed, "SEED_ROOT", root)
    call_command("export_projects_seed")
    exported = json.loads((root / "data.json").read_text())["projects"]
    assert len([item for item in exported if item["cover"]]) == 1
    Project.objects.all().delete()
    monkeypatch.setattr(seed_projects, "SEED_ROOT", root)
    call_command("seed_projects")
    restored = Project.objects.get(display_order=project.display_order)
    assert restored.status == Project.Status.DRAFT
    assert not restored.is_featured
    assert restored.end_year == project.end_year
    assert restored.published_at == project.published_at
    assert restored.website_url == project.website_url
    assert restored.translations.get(language="pt-br").seo_title == "SEO preservado"
    assert ProjectTeamMember.objects.count() == 54
    with Image.open(restored.cover.path) as cover:
        assert cover.format == "WEBP"
        assert cover.size == (200, 300)


@pytest.mark.django_db
def test_empty_export_preserves_existing_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(export_projects_seed, "SEED_ROOT", tmp_path)
    manifest = tmp_path / "data.json"
    manifest.write_text("Seed existente")
    with pytest.raises(CommandError, match="Nenhum projeto"):
        call_command("export_projects_seed")
    assert manifest.read_text() == "Seed existente"
