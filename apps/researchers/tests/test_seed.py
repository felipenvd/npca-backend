import json
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.fields.files import FieldFile
from PIL import Image

from apps.researchers.management.commands import export_researchers_seed, seed_researchers
from apps.researchers.models import Researcher, ResearcherTranslation


@pytest.fixture
def seed_settings(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings):
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


@pytest.mark.django_db
def test_seed_restores_all_researchers_translations_originals_and_crops(seed_settings, client):
    source = json.loads((seed_researchers.SEED_ROOT / "data.json").read_text())
    output = StringIO()
    call_command("seed_researchers", stdout=output)

    assert Researcher.objects.count() == 15
    assert ResearcherTranslation.objects.count() == 30
    assert len(media_files(seed_settings)) == 29
    assert "15 criados; 0 existentes preservados" in output.getvalue()
    for entry in source["researchers"]:
        researcher = Researcher.objects.get(full_name=entry["full_name"])
        for name in seed_researchers.RESEARCHER_FIELDS:
            assert getattr(researcher, name) == entry[name]
        for name in seed_researchers.PHOTO_FIELDS:
            field = getattr(researcher, name)
            if entry[name] is None:
                assert not field
            else:
                with field.open("rb") as image:
                    assert (
                        image.read()
                        == (seed_researchers.SEED_ROOT / "photos" / entry[name]).read_bytes()
                    )
        for translation in entry["translations"]:
            saved = researcher.translations.get(language=translation["language"])
            for name in seed_researchers.TRANSLATION_FIELDS:
                assert getattr(saved, name) == translation[name]
        if researcher.is_active:
            researcher.validate_for_activation()

    undergraduate = Researcher.objects.filter(academic_category="undergraduate_researcher").first()
    assert not undergraduate.translations.first().biography_html
    for lang in ("pt-br", "en"):
        response = client.get("/api/v1/researchers", {"lang": lang})
        assert response.status_code == 200
        assert response.json()["total"] == 15
        assert all(item["photo"]["url"].startswith("/media/") for item in response.json()["items"])


@pytest.mark.django_db
def test_seed_rerun_preserves_editorial_changes_and_unrelated_records(seed_settings):
    other = Researcher.objects.create(full_name="Outro pesquisador", academic_category="doctor")
    call_command("seed_researchers")
    researcher = Researcher.objects.get(full_name="Marcus de Barros Braga")
    researcher.full_name = "Nome editado no admin"
    researcher.display_order = 100
    researcher.is_active = False
    researcher.save()
    translation = researcher.translations.get(language="pt-br")
    translation.biography_html = "<p>Texto editorial atualizado.</p>"
    translation.save()
    files = media_files(seed_settings)
    output = StringIO()

    call_command("seed_researchers", stdout=output)

    assert Researcher.objects.count() == 16
    assert Researcher.objects.filter(pk=other.pk).exists()
    researcher.refresh_from_db()
    translation.refresh_from_db()
    assert researcher.full_name == "Nome editado no admin"
    assert researcher.display_order == 100
    assert researcher.is_active is False
    assert translation.biography_html == "<p>Texto editorial atualizado.</p>"
    assert media_files(seed_settings) == files
    assert "0 criados; 15 existentes preservados" in output.getvalue()


@pytest.mark.django_db
def test_missing_photo_fails_before_writing_database_or_media(seed_settings, tmp_path, monkeypatch):
    root = tmp_path / "seed"
    root.mkdir()
    (root / "data.json").write_bytes((seed_researchers.SEED_ROOT / "data.json").read_bytes())
    monkeypatch.setattr(seed_researchers, "SEED_ROOT", root)

    with pytest.raises(CommandError, match="Não foi possível carregar a foto"):
        call_command("seed_researchers")

    assert not Researcher.objects.exists()
    assert not media_files(seed_settings)


@pytest.mark.django_db
def test_storage_failure_rolls_back_new_records_and_files(seed_settings, monkeypatch):
    original_save = FieldFile.save
    calls = 0

    def fail_after_first(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("read-only file system")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(FieldFile, "save", fail_after_first)
    with pytest.raises(CommandError, match="MEDIA_ROOT"):
        call_command("seed_researchers")
    assert not Researcher.objects.exists()
    assert not ResearcherTranslation.objects.exists()
    assert not media_files(seed_settings)


@pytest.mark.django_db
def test_seed_rejects_conflicting_existing_names_and_slugs(seed_settings):
    source = json.loads((seed_researchers.SEED_ROOT / "data.json").read_text())["researchers"][0]
    Researcher.objects.create(full_name=source["full_name"], academic_category="doctor")
    other = Researcher.objects.create(full_name="Nome diferente", academic_category="doctor")
    ResearcherTranslation.objects.create(
        researcher=other, language="pt-br", slug=source["translations"][0]["slug"]
    )

    with pytest.raises(CommandError, match="Cadastros conflitantes"):
        call_command("seed_researchers")
    assert Researcher.objects.count() == 2
    assert not media_files(seed_settings)


@pytest.mark.django_db
def test_export_recreates_a_portable_seed_with_exact_current_data(
    seed_settings, tmp_path, monkeypatch
):
    call_command("seed_researchers")
    root = tmp_path / "export"
    monkeypatch.setattr(export_researchers_seed, "SEED_ROOT", root)
    call_command("export_researchers_seed")

    payload = seed_researchers.load_seed_payload(root)
    assert len(payload) == 15
    assert len(list((root / "photos").iterdir())) == 29
    # Restore the export in an empty database; MEDIA_ROOT contains existing uploads.
    Researcher.objects.all().delete()
    monkeypatch.setattr(seed_researchers, "SEED_ROOT", root)
    call_command("seed_researchers")
    assert Researcher.objects.count() == 15
    for item in payload:
        researcher = Researcher.objects.get(full_name=item.values["full_name"])
        assert researcher.photo_crop == item.values["photo_crop"]
        for name, path in item.photos.items():
            with getattr(researcher, name).open("rb") as image:
                assert image.read() == path.read_bytes()


@pytest.mark.django_db
def test_empty_export_keeps_existing_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(export_researchers_seed, "SEED_ROOT", tmp_path)
    manifest = tmp_path / "data.json"
    manifest.write_text("seed existente")
    with pytest.raises(CommandError, match="Nenhum pesquisador"):
        call_command("export_researchers_seed")
    assert manifest.read_text() == "seed existente"


@pytest.mark.django_db
def test_export_does_not_replace_seed_when_a_source_photo_is_missing(
    seed_settings, tmp_path, monkeypatch
):
    researcher = Researcher.objects.create(full_name="Ana Silva", academic_category="doctor")
    researcher.photo.save("test.webp", ContentFile(b"missing source"))
    Path(researcher.photo.path).unlink()
    root = tmp_path / "export"
    root.mkdir()
    (root / "data.json").write_text("seed existente")
    monkeypatch.setattr(export_researchers_seed, "SEED_ROOT", root)
    with pytest.raises(CommandError, match="Não foi possível exportar"):
        call_command("export_researchers_seed")
    assert (root / "data.json").read_text() == "seed existente"
    assert not (root / "photos").exists()


def test_webp_conversion_preserves_orientation_and_complete_image():
    image = Image.new("RGB", (400, 200), "blue")
    image.paste("red", (0, 0, 200, 200))
    exif = Image.Exif()
    exif[274] = 6
    source = BytesIO()
    image.save(source, "JPEG", exif=exif)

    converted = export_researchers_seed.webp_image(source.getvalue())

    with Image.open(BytesIO(converted)) as result:
        assert result.format == "WEBP"
        assert result.size == (200, 400)
        assert result.getexif().get(274) is None
        assert result.getpixel((100, 100))[0] > 240
        assert result.getpixel((100, 300))[2] > 240
    assert export_researchers_seed.webp_image(converted) == converted


def test_webp_conversion_preserves_palette_transparency():
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0)).convert("P")
    source = BytesIO()
    image.save(source, "PNG")
    result = export_researchers_seed.webp_image(source.getvalue())
    with Image.open(BytesIO(result)) as converted:
        assert converted.mode == "RGBA"
        assert converted.getpixel((0, 0))[3] == 0


@pytest.mark.django_db
def test_export_replaces_old_seed_photos_with_webp_and_keeps_current_crop(
    seed_settings, tmp_path, monkeypatch
):
    source = BytesIO()
    Image.new("RGB", (600, 900), "red").save(source, "JPEG")
    cropped = BytesIO()
    Image.new("RGB", (512, 512), "red").save(cropped, "WEBP")
    researcher = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category="doctor",
        photo_crop={"x": 50, "y": 10, "zoom": 1.5},
    )
    researcher.photo.save("ana.jpg", ContentFile(source.getvalue()))
    researcher.photo_cropped.save("ana-cropped.webp", ContentFile(cropped.getvalue()))
    original_name = researcher.photo.name
    root = tmp_path / "export"
    photos = root / "photos"
    photos.mkdir(parents=True)
    obsolete = photos / "ana-silva.jpg"
    obsolete.write_bytes(source.getvalue())
    unrelated = photos / "unrelated.png"
    unrelated.write_bytes(b"keep this file")
    (root / "data.json").write_text(
        json.dumps(
            {"researchers": [{"photo": "ana-silva.jpg", "photo_cropped": "ana-silva-cropped.webp"}]}
        )
    )
    monkeypatch.setattr(export_researchers_seed, "SEED_ROOT", root)

    call_command("export_researchers_seed")

    entry = json.loads((root / "data.json").read_text())["researchers"][0]
    assert entry["photo"] == "ana-silva.webp"
    assert entry["photo_crop"] == researcher.photo_crop
    assert not obsolete.exists()
    assert unrelated.read_bytes() == b"keep this file"
    assert (photos / entry["photo_cropped"]).read_bytes() == cropped.getvalue()
    with Image.open(photos / entry["photo"]) as image:
        assert image.format == "WEBP"
        assert image.size == (600, 900)
    researcher.refresh_from_db()
    assert researcher.photo.name == original_name
    assert researcher.photo.read() == source.getvalue()
