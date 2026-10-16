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

from apps.projects.models import Project, ProjectTranslation
from apps.publications.management.commands import export_publications_seed, seed_publications
from apps.publications.models import Publication, PublicationAuthor, PublicationTranslation
from apps.researchers.models import Researcher


@pytest.fixture(autouse=True)
def seed_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings):
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


def seed_records():
    return json.loads((seed_publications.SEED_ROOT / "data.json").read_text())["publications"]


def create_researchers():
    names = {
        author["researcher"]
        for entry in seed_records()
        for author in entry["authors"]
        if author["researcher"]
    }
    for name in sorted(names):
        Researcher.objects.create(
            full_name=name, academic_category=Researcher.AcademicCategory.DOCTOR
        )


def write_seed(tmp_path, monkeypatch, records):
    (tmp_path / "data.json").write_text(json.dumps({"publications": records}), encoding="utf-8")
    monkeypatch.setattr(seed_publications, "SEED_ROOT", tmp_path)


@pytest.mark.django_db
def test_real_seed_restores_bilingual_publications_ordered_authors_and_webp_covers(
    seed_media, client
):
    source = seed_records()
    Researcher.objects.create(
        full_name="Cadastro que desloca os IDs",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    create_researchers()

    call_command("seed_publications")

    assert Publication.objects.count() == 4
    assert PublicationTranslation.objects.count() == 8
    assert PublicationAuthor.objects.count() == 36
    assert len(media_files(seed_media)) == 4
    for entry in source:
        publication = Publication.objects.get(doi=entry["doi"])
        for field in seed_publications.MODEL_FIELDS:
            expected = entry[field]
            if field == "published_at" and expected:
                expected = datetime.fromisoformat(expected)
            assert getattr(publication, field) == expected
        for translation in entry["translations"]:
            saved = publication.translations.get(language=translation["language"])
            assert all(getattr(saved, field) == value for field, value in translation.items())
        authors = [
            {
                "researcher": author.researcher.full_name if author.researcher else None,
                "external_name": author.external_name,
                "display_order": author.display_order,
            }
            for author in publication.author_records.select_related("researcher")
        ]
        assert authors == entry["authors"]
        with publication.cover.open("rb") as cover:
            assert (
                cover.read()
                == (seed_publications.SEED_ROOT / "covers" / entry["cover"]).read_bytes()
            )
        with Image.open(publication.cover.path) as image:
            assert image.format == "WEBP"
        publication.validate_for_publication()
    for language in ("pt-br", "en"):
        response = client.get("/api/v1/publications", {"lang": language})
        assert response.status_code == 200
        assert response.json()["total"] == 4
        assert all(item["cover"]["url"].endswith(".webp") for item in response.json()["items"])

    publication = Publication.objects.first()
    publication.translations.filter(language="pt-br").update(title="Edição preservada")
    files = media_files(seed_media)
    output = StringIO()
    call_command("seed_publications", stdout=output)
    assert "0 criadas; 4 existentes preservadas" in output.getvalue()
    assert Publication.objects.count() == 4
    assert publication.translations.get(language="pt-br").title == "Edição preservada"
    assert media_files(seed_media) == files


@pytest.mark.django_db
def test_existing_publication_is_preserved_while_missing_ones_are_created(seed_media):
    create_researchers()
    source = seed_records()[0]
    publication = Publication.objects.create(doi=source["doi"], venue="Edição manual")

    call_command("seed_publications")

    publication.refresh_from_db()
    assert publication.venue == "Edição manual"
    assert publication.status == Publication.Status.DRAFT
    assert not publication.author_records.exists()
    assert Publication.objects.count() == 4
    assert len(media_files(seed_media)) == 3


@pytest.mark.django_db
@pytest.mark.parametrize("ambiguous", [False, True])
def test_missing_or_ambiguous_researcher_prevents_all_writes(ambiguous, seed_media):
    if ambiguous:
        create_researchers()
        Researcher.objects.create(
            full_name=Researcher.objects.first().full_name,
            academic_category=Researcher.AcademicCategory.DOCTOR,
        )
    with pytest.raises(CommandError, match="Execute seed_researchers"):
        call_command("seed_publications")
    assert not Publication.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "invalid", "opção válida"),
        ("year", True, "deve ser inteiro"),
        ("doi", "invalid", "DOI válido"),
        ("cover", "missing.webp", "Não foi possível carregar a capa"),
        ("cover", "../outside.webp", "somente o nome"),
        ("authors", [], "pelo menos um autor"),
        ("translations", [], "tradução"),
    ],
)
def test_invalid_seed_fails_before_writes(tmp_path, monkeypatch, seed_media, field, value, message):
    records = seed_records()
    records[0][field] = value
    write_seed(tmp_path, monkeypatch, records)
    with pytest.raises(CommandError, match=message):
        call_command("seed_publications")
    assert not Publication.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_duplicate_author_orders_are_rejected_before_writes(tmp_path, monkeypatch):
    records = seed_records()
    records[0]["authors"][1]["display_order"] = records[0]["authors"][0]["display_order"]
    write_seed(tmp_path, monkeypatch, records)
    with pytest.raises(CommandError, match="ordens dos autores"):
        call_command("seed_publications")
    assert not Publication.objects.exists()


@pytest.mark.django_db
def test_storage_failure_rolls_back_publications_authors_translations_and_new_covers(
    monkeypatch, seed_media
):
    create_researchers()
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
        call_command("seed_publications")
    assert not Publication.objects.exists()
    assert not PublicationTranslation.objects.exists()
    assert not PublicationAuthor.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_export_round_trip_preserves_project_authors_dates_and_converts_cover(
    tmp_path, monkeypatch
):
    create_researchers()
    call_command("seed_publications")
    publication = Publication.objects.first()
    publication.status = Publication.Status.DRAFT
    publication.display_order = 99
    project = Project.objects.create()
    ProjectTranslation.objects.create(
        project=project, language="pt-br", title="Projeto de pesquisa"
    )
    publication.project = project
    image = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image, "PNG")
    publication.cover.save("new-cover.png", ContentFile(image.getvalue()), save=False)
    publication.save()
    publication.translations.filter(language="pt-br").update(
        seo_title="SEO preservado", seo_description="Descrição preservada"
    )
    root = tmp_path / "export"
    monkeypatch.setattr(export_publications_seed, "SEED_ROOT", root)

    call_command("export_publications_seed")

    exported = json.loads((root / "data.json").read_text())["publications"]
    assert all(item["cover"].endswith(".webp") for item in exported)
    Publication.objects.all().delete()
    monkeypatch.setattr(seed_publications, "SEED_ROOT", root)
    call_command("seed_publications")

    restored = Publication.objects.get(doi=publication.doi)
    assert restored.status == Publication.Status.DRAFT
    assert restored.display_order == 99
    assert restored.published_at == publication.published_at
    assert restored.project == project
    assert restored.translations.get(language="pt-br").seo_title == "SEO preservado"
    assert PublicationAuthor.objects.count() == 36
    with Image.open(restored.cover.path) as cover:
        assert cover.format == "WEBP"
        assert cover.size == (200, 300)


@pytest.mark.django_db
def test_empty_export_preserves_existing_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(export_publications_seed, "SEED_ROOT", tmp_path)
    manifest = tmp_path / "data.json"
    manifest.write_text("Seed existente")
    with pytest.raises(CommandError, match="Nenhuma publicação"):
        call_command("export_publications_seed")
    assert manifest.read_text() == "Seed existente"
