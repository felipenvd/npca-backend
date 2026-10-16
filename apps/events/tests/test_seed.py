import json
import shutil
from datetime import date, datetime, time
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.fields.files import FieldFile
from PIL import Image

from apps.events.management.commands import export_events_seed, seed_events
from apps.events.models import Event, EventTranslation


@pytest.fixture(autouse=True)
def seed_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings


def media_files(settings):
    return {path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()}


def seed_records():
    return json.loads((seed_events.SEED_ROOT / "data.json").read_text())["events"]


def write_seed(root, monkeypatch, records):
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed_events.SEED_ROOT / "covers", root / "covers", dirs_exist_ok=True)
    (root / "data.json").write_text(json.dumps({"events": records}), encoding="utf-8")
    monkeypatch.setattr(seed_events, "SEED_ROOT", root)


@pytest.mark.django_db
def test_real_seed_restores_all_events_translations_images_and_framing(client, seed_media):
    records = seed_records()
    call_command("seed_events")

    assert Event.objects.count() == 4
    assert EventTranslation.objects.count() == 8
    assert len(media_files(seed_media)) == 4
    parsers = {
        "start_date": date.fromisoformat,
        "end_date": date.fromisoformat,
        "start_time": time.fromisoformat,
        "end_time": time.fromisoformat,
        "published_at": datetime.fromisoformat,
    }
    for entry in records:
        event = Event.objects.get(display_order=entry["display_order"])
        for field in seed_events.MODEL_FIELDS:
            expected = entry[field]
            if field in parsers and expected is not None:
                expected = parsers[field](expected)
            assert getattr(event, field) == expected
        for translation in entry["translations"]:
            saved = event.translations.get(language=translation["language"])
            assert all(getattr(saved, field) == value for field, value in translation.items())
        with event.cover.open("rb") as saved:
            assert saved.read() == (seed_events.SEED_ROOT / "covers" / entry["cover"]).read_bytes()
            event.full_clean()
        event.validate_for_publication()
    assert Event.objects.filter(start_time__isnull=True, end_time__isnull=True).count() == 2
    course = Event.objects.get(event_type=Event.EventType.COURSE)
    assert course.online_url == ""
    for language in ("pt-br", "en"):
        listing = client.get("/api/v1/events", {"lang": language, "period": "all", "page_size": 15})
        assert listing.status_code == 200
        assert listing.json()["total"] == 4
        for item in listing.json()["items"]:
            detail = client.get(f"/api/v1/events/{item['slug']}", {"lang": language})
            assert detail.status_code == 200
            assert detail.json()["cover"] == item["cover"]
            event = Event.objects.get(
                translations__language=language, translations__slug=item["slug"]
            )
            assert item["cover"]["zoom"] == event.cover_zoom
            assert item["cover"]["position_x"] == event.cover_position_x
            assert item["cover"]["position_y"] == event.cover_position_y

    event = Event.objects.first()
    event.cover_zoom = 200
    event.cover_credit = "Crédito editado no admin"
    event.save()
    event.translations.filter(language="pt-br").update(title="Edição manual preservada")
    before = media_files(seed_media)
    output = StringIO()
    call_command("seed_events", stdout=output)
    assert "0 criados; 4 existentes preservados" in output.getvalue()
    assert Event.objects.count() == 4
    assert EventTranslation.objects.count() == 8
    assert media_files(seed_media) == before
    event.refresh_from_db()
    assert event.cover_zoom == 200
    assert event.cover_credit == "Crédito editado no admin"
    assert event.translations.get(language="pt-br").title == "Edição manual preservada"


@pytest.mark.django_db
def test_partial_seed_preserves_existing_and_creates_missing(seed_media):
    translation = seed_records()[0]["translations"][0]
    event = Event.objects.create(cover_zoom=150, cover_credit="Edição manual")
    EventTranslation.objects.create(event=event, **translation)
    call_command("seed_events")
    event.refresh_from_db()
    assert event.status == Event.Status.DRAFT
    assert event.cover_zoom == 150
    assert event.cover_credit == "Edição manual"
    assert event.translations.count() == 1
    assert not event.cover
    assert Event.objects.count() == 4
    assert len(media_files(seed_media)) == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "invalid", "não é uma opção válida"),
        ("display_order", True, "inteiro"),
        ("cover_zoom", 99, "100"),
        ("cover_zoom", 301, "300"),
        ("cover_position_x", 101, "100"),
        ("cover_position_y", -1, "0"),
        ("is_all_day", "false", "booleano"),
        ("start_date", "not-a-date", "formato ISO"),
        ("end_date", "2025-02-31", "formato ISO"),
        ("end_date", "2020-01-01", "posterior"),
        ("end_date", "2100-01-01", "realizado"),
        ("start_time", "25:00:00", "formato ISO"),
        ("published_at", "2026-01-01T12:00:00", "fuso horário"),
        ("translations", [], "título ou slug"),
        ("cover", "missing.webp", "carregar a capa"),
        ("cover", "../outside.webp", "somente o nome"),
    ],
)
def test_invalid_payload_fails_before_any_writes(
    tmp_path, monkeypatch, seed_media, field, value, message
):
    records = seed_records()
    records[-1][field] = value
    write_seed(tmp_path / "seed", monkeypatch, records)
    with pytest.raises(CommandError, match=message):
        call_command("seed_events")
    assert not Event.objects.exists()
    assert not EventTranslation.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
@pytest.mark.parametrize("invalid", ["slug", "language", "translation", "location"])
def test_invalid_translations_fail_before_writes(tmp_path, monkeypatch, seed_media, invalid):
    records = seed_records()
    if invalid == "slug":
        records[-1]["translations"][0]["slug"] = records[0]["translations"][0]["slug"]
        message = "Evento duplicado"
    elif invalid == "language":
        records[-1]["translations"].append(records[-1]["translations"][0].copy())
        message = "Idioma duplicado"
    elif invalid == "translation":
        records[-1]["translations"] = records[-1]["translations"][:1]
        message = "tradução"
    else:
        records[-1]["translations"][0]["location_name"] = ""
        message = "nome do local"
    write_seed(tmp_path / "seed", monkeypatch, records)
    with pytest.raises(CommandError, match=message):
        call_command("seed_events")
    assert not Event.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_conflicting_existing_translations_prevent_all_writes(seed_media):
    for translation in seed_records()[-1]["translations"]:
        EventTranslation.objects.create(event=Event.objects.create(), **translation)
    with pytest.raises(CommandError, match="conflitantes"):
        call_command("seed_events")
    assert Event.objects.count() == 2
    assert EventTranslation.objects.count() == 2
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_storage_failure_rolls_back_events_translations_and_new_covers(monkeypatch, seed_media):
    original_save = FieldFile.save
    calls = 0

    def fail_on_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Storage indisponível")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(FieldFile, "save", fail_on_second)
    with pytest.raises(CommandError, match="MEDIA_ROOT"):
        call_command("seed_events")
    assert not Event.objects.exists()
    assert not EventTranslation.objects.exists()
    assert not media_files(seed_media)


@pytest.mark.django_db
def test_export_round_trip_preserves_draft_optional_times_links_zoom_and_webp(
    tmp_path, monkeypatch
):
    call_command("seed_events")
    event = Event.objects.first()
    event.status = Event.Status.DRAFT
    event.start_time = event.end_time = None
    event.online_url = "https://example.org/watch"
    event.registration_url = "https://example.org/register"
    event.cover_zoom = 175
    event.cover_position_x, event.cover_position_y = 22, 81
    image = BytesIO()
    Image.new("RGB", (200, 300), "white").save(image, "PNG")
    event.cover.save("new-cover.png", ContentFile(image.getvalue()), save=False)
    event.save()
    event.translations.filter(language="pt-br").update(seo_title="SEO preservado")
    root = tmp_path / "export"
    monkeypatch.setattr(export_events_seed, "SEED_ROOT", root)
    call_command("export_events_seed")
    exported = json.loads((root / "data.json").read_text())["events"]
    assert len(exported) == 4
    assert len(list((root / "covers").glob("*.webp"))) == 4
    Event.objects.all().delete()
    monkeypatch.setattr(seed_events, "SEED_ROOT", root)
    call_command("seed_events")
    restored = Event.objects.get(display_order=event.display_order)
    assert restored.status == Event.Status.DRAFT
    assert restored.published_at == event.published_at
    assert restored.start_time is restored.end_time is None
    assert restored.online_url == event.online_url
    assert restored.registration_url == event.registration_url
    assert restored.cover_zoom == 175
    assert (restored.cover_position_x, restored.cover_position_y) == (22, 81)
    assert restored.translations.get(language="pt-br").seo_title == "SEO preservado"
    assert EventTranslation.objects.count() == 8
    with Image.open(restored.cover.path) as cover:
        assert cover.format == "WEBP"
        assert cover.size == (200, 300)


@pytest.mark.django_db
def test_empty_export_preserves_existing_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(export_events_seed, "SEED_ROOT", tmp_path)
    manifest = tmp_path / "data.json"
    manifest.write_text("Seed existente")
    with pytest.raises(CommandError, match="Nenhum evento"):
        call_command("export_events_seed")
    assert manifest.read_text() == "Seed existente"
