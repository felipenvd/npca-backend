from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.events.models import Event, EventTranslation


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("event.webp", buffer.getvalue(), content_type="image/webp")


def create_event(
    *,
    title: str,
    day_offset: int,
    order: int = 0,
    event_type: str = Event.EventType.SEMINAR,
    schedule_status: str = Event.ScheduleStatus.SCHEDULED,
    status: str = Event.Status.PUBLISHED,
    cover=None,
) -> Event:
    event_date = timezone.localdate() + timedelta(days=day_offset)
    event = Event.objects.create(
        status=status,
        schedule_status=schedule_status,
        event_type=event_type,
        modality=Event.Modality.HYBRID,
        start_date=event_date,
        end_date=event_date,
        is_all_day=True,
        online_url="https://meet.example.com/event",
        registration_url="https://register.example.com/event",
        cover=cover,
        cover_credit="NPCA" if cover else "",
        display_order=order,
    )
    EventTranslation.objects.create(
        event=event,
        language="pt-br",
        title=title,
        summary=f"Resumo de {title}",
        body_html="<p>Descrição</p>",
        location_name="Auditório principal",
        location_address="Campus UFRA",
        cover_alt_text="Pessoas em um auditório" if cover else "",
    )
    EventTranslation.objects.create(
        event=event,
        language="en",
        title=f"{title} EN",
        summary=f"Summary of {title}",
        body_html="<p>Description</p>",
        location_name="Main auditorium",
        location_address="UFRA campus",
        cover_alt_text="People in an auditorium" if cover else "",
    )
    return event


@pytest.mark.django_db
def test_list_requires_language_and_valid_filters(client) -> None:
    assert client.get("/api/v1/events").status_code == 422
    assert client.get("/api/v1/events", {"lang": "fr"}).status_code == 422
    assert client.get("/api/v1/events", {"lang": "pt-br", "period": "future"}).status_code == 422
    assert client.get("/api/v1/events", {"lang": "pt-br", "page_size": 51}).status_code == 422


@pytest.mark.django_db
def test_upcoming_orders_ongoing_first_and_filters_type(client) -> None:
    create_event(title="Futuro B", day_offset=2, order=2)
    create_event(title="Futuro A", day_offset=2, order=1)
    create_event(title="Hoje", day_offset=0)
    create_event(title="Passado", day_offset=-1)
    create_event(title="Curso", day_offset=1, event_type=Event.EventType.COURSE)

    response = client.get(
        "/api/v1/events",
        {"lang": "pt-br", "period": "upcoming", "page_size": 10},
    )
    filtered = client.get(
        "/api/v1/events",
        {"lang": "pt-br", "period": "upcoming", "type": "course"},
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == [
        "Hoje",
        "Curso",
        "Futuro A",
        "Futuro B",
    ]
    assert [item["title"] for item in filtered.json()["items"]] == ["Curso"]


@pytest.mark.django_db
def test_past_order_and_cancel_visibility(client) -> None:
    create_event(title="Mais antigo", day_offset=-3)
    create_event(title="Mais recente", day_offset=-1)
    create_event(
        title="Cancelado",
        day_offset=1,
        schedule_status=Event.ScheduleStatus.CANCELED,
    )

    past = client.get("/api/v1/events", {"lang": "pt-br", "period": "past"})
    with_canceled = client.get(
        "/api/v1/events",
        {"lang": "pt-br", "period": "upcoming"},
    )
    without_canceled = client.get(
        "/api/v1/events",
        {"lang": "pt-br", "period": "upcoming", "include_canceled": "false"},
    )

    assert [item["title"] for item in past.json()["items"]] == [
        "Mais recente",
        "Mais antigo",
    ]
    assert with_canceled.json()["total"] == 1
    assert without_canceled.json()["total"] == 0


@pytest.mark.django_db
def test_detail_returns_schedule_location_registration_cover_and_translations(
    client,
    settings,
    tmp_path,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    event = create_event(title="Seminário", day_offset=1, cover=webp_upload())

    response = client.get("/api/v1/events/seminario", {"lang": "pt-br"})

    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "seminar"
    assert body["temporal_state"] == "upcoming"
    assert body["location"] == {
        "modality": "hybrid",
        "name": "Auditório principal",
        "address": "Campus UFRA",
        "online_url": "https://meet.example.com/event",
    }
    assert body["registration_url"] == "https://register.example.com/event"
    assert body["cover"] == {
        "url": f"/media/{event.cover.name}",
        "alt": "Pessoas em um auditório",
        "credit": "NPCA",
    }
    assert body["translations"] == [
        {"lang": "en", "slug": "seminario-en"},
        {"lang": "pt-br", "slug": "seminario"},
    ]


@pytest.mark.django_db
def test_detail_hides_draft_and_wrong_language_slug(client) -> None:
    published = create_event(title="Publicado", day_offset=1)
    draft = create_event(title="Rascunho", day_offset=1, status=Event.Status.DRAFT)

    wrong_language = client.get("/api/v1/events/publicado", {"lang": "en"})
    hidden = client.get(
        f"/api/v1/events/{draft.translations.get(language='pt-br').slug}",
        {"lang": "pt-br"},
    )

    assert published.status == Event.Status.PUBLISHED
    assert wrong_language.status_code == 404
    assert hidden.status_code == 404
    assert hidden["Content-Type"] == "application/problem+json"
