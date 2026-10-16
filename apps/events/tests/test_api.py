from datetime import datetime, time, timedelta
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

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
        "position_x": 50,
        "position_y": 50,
        "zoom": 100,
    }
    assert body["translations"] == [
        {"lang": "en", "slug": "seminario-en"},
        {"lang": "pt-br", "slug": "seminario"},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("modality", [Event.Modality.ONLINE, Event.Modality.HYBRID])
def test_published_event_without_online_url_returns_null_in_both_languages(client, modality):
    event = create_event(title="Sem link público", day_offset=-1)
    event.modality = modality
    event.online_url = ""
    event.save()

    for language in ("pt-br", "en"):
        slug = event.translations.get(language=language).slug
        listing = client.get("/api/v1/events", {"lang": language, "period": "past"})
        detail = client.get(f"/api/v1/events/{slug}", {"lang": language})
        assert listing.status_code == detail.status_code == 200
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["location"]["online_url"] is None
        assert detail.json()["location"]["online_url"] is None


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


@pytest.mark.django_db
@pytest.mark.parametrize("start_time", [None, time(9)])
@pytest.mark.parametrize("end_time", [None, time(11)])
@pytest.mark.parametrize("hour", [8, 9, 11, 23])
def test_filters_and_details_agree_with_optional_time_boundaries(
    client, start_time, end_time, hour
):
    event = create_event(title="Horários opcionais", day_offset=0)
    event.is_all_day = False
    event.start_time = start_time
    event.end_time = end_time
    event.full_clean()
    event.save()
    reference = datetime.combine(event.start_date, time(hour), tzinfo=ZoneInfo("America/Belem"))
    expected = (
        "past"
        if end_time and hour >= end_time.hour
        else "upcoming"
        if start_time and hour < start_time.hour
        else "ongoing"
    )
    with patch("apps.events.api.timezone.now", return_value=reference):
        for language in ("pt-br", "en"):
            slug = event.translations.get(language=language).slug
            for period in ("upcoming", "past", "all"):
                response = client.get("/api/v1/events", {"lang": language, "period": period})
                assert response.status_code == 200
                included = period == "all" or (period == "past") == (expected == "past")
                assert response.json()["total"] == int(included)
                if included:
                    assert response.json()["items"][0]["temporal_state"] == expected
            detail = client.get(f"/api/v1/events/{slug}", {"lang": language})
            assert detail.status_code == 200
            assert detail.json()["temporal_state"] == expected
            assert detail.json()["is_all_day"] is False
            assert detail.json()["start_time"] == (start_time.isoformat() if start_time else None)
            assert detail.json()["end_time"] == (end_time.isoformat() if end_time else None)


@pytest.mark.django_db
def test_completed_event_is_returned_in_past_lists_and_bilingual_details(client) -> None:
    event = create_event(
        title="Evento realizado",
        day_offset=-1,
        schedule_status=Event.ScheduleStatus.COMPLETED,
    )
    for language in ("pt-br", "en"):
        slug = event.translations.get(language=language).slug
        past = client.get("/api/v1/events", {"lang": language, "period": "past"})
        upcoming = client.get("/api/v1/events", {"lang": language, "period": "upcoming"})
        detail = client.get(f"/api/v1/events/{slug}", {"lang": language})

        assert past.status_code == detail.status_code == 200
        assert past.json()["items"][0]["schedule_status"] == "completed"
        assert past.json()["items"][0]["temporal_state"] == "past"
        assert upcoming.json()["total"] == 0
        assert detail.json()["schedule_status"] == "completed"
