from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse
from PIL import Image

from apps.core.tests.test_bilingual_admin import FormValues
from apps.events.forms import EventForm
from apps.events.models import Event
from apps.events.tests.test_admin import event_data
from apps.events.tests.test_api import create_event


def portrait():
    buffer = BytesIO()
    Image.new("RGB", (240, 400), "#008a83").save(buffer, "WEBP")
    return SimpleUploadedFile("portrait.webp", buffer.getvalue(), content_type="image/webp")


def test_zoom_slider_limits_match_validation():
    html = str(EventForm()["cover_zoom"])
    assert 'min="100"' in html
    assert 'max="300"' in html
    assert 'step="5"' in html
    assert 'value="100"' in html


@pytest.mark.django_db
def test_admin_saves_cover_position_and_preserves_original(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    data = event_data(published=False, complete_english=True)
    data.pop("_event_date")
    upload = portrait()
    original = upload.read()
    upload.seek(0)
    data.update(cover=upload, cover_position_x="25", cover_position_y="0", cover_zoom="175")

    response = admin_client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 302
    event = Event.objects.get()
    assert event.cover_position_x == 25
    assert event.cover_position_y == 0
    assert event.cover_zoom == 175
    with event.cover.open("rb") as saved:
        assert saved.read() == original
    image_name = event.cover.name
    url = reverse("admin:events_event_change", args=[event.pk])
    page = admin_client.get(url)
    html = page.content.decode()
    assert "events/admin/cover_editor.js" in html
    assert "events/admin/cover_editor.css" in html
    assert "Prévia do card" in html
    assert "Imagem na página do evento" in html
    assert 'type="range"' in html
    assert "data-event-cover-editor" in html
    assert "cover_fit" not in html
    assert "Mostrar imagem inteira" not in html
    assert "O mesmo recorte do card será usado" in html
    assert 'id="id_cover_zoom"' in html
    assert "--cover-zoom: 175" in html
    values = FormValues(html, "event_form").values
    values.update(cover_position_x="100", cover_position_y="15", cover_zoom="250", _save="Salvar")
    assert admin_client.post(url, values).status_code == 302
    event.refresh_from_db()
    assert event.cover_position_x == 100
    assert event.cover_position_y == 15
    assert event.cover_zoom == 250
    with event.cover.open("rb") as saved:
        assert saved.read() == original
    assert event.cover.name == image_name
    assert len(list(tmp_path.rglob("*.webp"))) == 1
    values["cover-clear"] = "on"
    assert admin_client.post(url, values).status_code == 302
    event.refresh_from_db()
    assert not event.cover


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [("cover_position_x", -1), ("cover_position_y", 101), ("cover_zoom", 99), ("cover_zoom", 301)],
)
def test_admin_rejects_invalid_cover_settings(admin_client, field, value):
    data = event_data(published=False)
    data.pop("_event_date")
    data[field] = value
    response = admin_client.post(reverse("admin:events_event_add"), data)
    assert response.status_code == 200
    assert field in response.context["adminform"].form.errors
    assert not Event.objects.exists()


@pytest.mark.django_db
def test_cover_position_is_validated_in_model_and_database():
    event = Event(cover_position_y=101)
    with pytest.raises(ValidationError):
        event.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        event.save()


@pytest.mark.django_db
@pytest.mark.parametrize("zoom", [99, 301])
def test_cover_zoom_is_validated_in_model_and_database(zoom):
    event = Event(cover_zoom=zoom)
    with pytest.raises(ValidationError) as error:
        event.full_clean()
    assert "cover_zoom" in error.value.message_dict
    with pytest.raises(IntegrityError), transaction.atomic():
        event.save()


@pytest.mark.django_db
@pytest.mark.parametrize("zoom", [100, 300])
def test_cover_zoom_accepts_limits(zoom):
    event = Event(cover_zoom=zoom)
    event.full_clean()
    event.save()
    event.refresh_from_db()
    assert event.cover_zoom == zoom


@pytest.mark.django_db
def test_cover_positions_reach_lists_and_details_in_both_languages(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    event = create_event(title="Enquadramento", day_offset=-1, cover=portrait())
    event.cover_position_x = 100
    event.cover_position_y = 0
    event.cover_zoom = 180
    event.save()
    for language in ("pt-br", "en"):
        listing = client.get("/api/v1/events", {"lang": language, "period": "all"})
        slug = event.translations.get(language=language).slug
        detail = client.get(f"/api/v1/events/{slug}", {"lang": language})
        assert listing.status_code == detail.status_code == 200
        cover = listing.json()["items"][0]["cover"]
        assert cover == detail.json()["cover"]
        assert "fit" not in cover
        assert cover["position_x"] == 100
        assert cover["position_y"] == 0
        assert cover["zoom"] == 180
