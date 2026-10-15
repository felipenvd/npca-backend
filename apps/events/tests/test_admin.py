from datetime import date, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event


def event_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    event_date = timezone.localdate() + timedelta(days=7)
    return {
        "status": Event.Status.PUBLISHED if published else Event.Status.DRAFT,
        "schedule_status": Event.ScheduleStatus.SCHEDULED,
        "event_type": "",
        "modality": "",
        "start_date": "",
        "end_date": "",
        "is_all_day": "on",
        "start_time": "",
        "end_time": "",
        "cover_credit": "",
        "online_url": "",
        "registration_url": "",
        "display_order": "0",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Seminário Amazônia",
        "translations-0-slug": "",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Descrição</p>",
        "translations-0-location_name": "",
        "translations-0-location_address": "",
        "translations-0-cover_alt_text": "",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-title": "Amazon Seminar" if complete_english else "",
        "translations-1-slug": "",
        "translations-1-summary": "Summary" if complete_english else "",
        "translations-1-body_html": "<p>Description</p>" if complete_english else "",
        "translations-1-location_name": "",
        "translations-1-location_address": "",
        "translations-1-cover_alt_text": "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "_save": "Salvar",
        "_event_date": event_date.strftime("%d/%m/%Y"),
    }


@pytest.mark.django_db
def test_admin_add_page_exposes_schedule_translations_and_media(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:events_event_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="translations-0-language" value="pt-br"' in content
    assert 'name="translations-1-language" value="en"' in content
    assert "Título *" in content
    assert "Descrição *" in content
    assert "Data de início *" in content
    assert "Evento de dia inteiro" in content
    assert "URL externa de inscrição" in content
    assert "Imagem de divulgação" in content
    assert "Texto alternativo da imagem" in content
    assert "unfold/forms/js/trix/trix.js" in content
    assert '<option value="completed">Realizado</option>' in content


@pytest.mark.django_db
def test_admin_allows_incomplete_draft_and_records_audit(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = event_data(published=False)
    data.pop("_event_date")

    response = client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 302
    event = Event.objects.get()
    assert event.created_by == admin_user
    assert event.updated_by == admin_user
    assert event.translations.get(language="pt-br").slug == "seminario-amazonia"


@pytest.mark.django_db
def test_admin_blocks_incomplete_publication_and_accepts_complete_hybrid_event(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = event_data(published=True)
    event_date = data.pop("_event_date")

    invalid_response = client.post(reverse("admin:events_event_add"), data)

    assert invalid_response.status_code == 200
    assert not Event.objects.exists()

    data.update(
        {
            "event_type": Event.EventType.SEMINAR,
            "modality": Event.Modality.HYBRID,
            "start_date": event_date,
            "end_date": event_date,
            "online_url": "https://meet.example.com/event",
            "translations-0-location_name": "Auditório",
            "translations-1-title": "Amazon Seminar",
            "translations-1-summary": "Summary",
            "translations-1-body_html": "<p>Description</p>",
            "translations-1-location_name": "Auditorium",
        }
    )
    valid_response = client.post(reverse("admin:events_event_add"), data)

    assert valid_response.status_code == 302
    event = Event.objects.get()
    assert event.status == Event.Status.PUBLISHED
    assert event.is_all_day is True
    assert event.published_at is not None


@pytest.mark.django_db
def test_admin_can_confirm_completed_event_and_rejects_future_event(admin_client) -> None:
    data = event_data(published=False)
    future_date = data.pop("_event_date")
    data.update(
        {
            "schedule_status": Event.ScheduleStatus.COMPLETED,
            "start_date": future_date,
            "end_date": future_date,
        }
    )

    response = admin_client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 200
    assert "schedule_status" in response.context["adminform"].form.errors
    assert not Event.objects.exists()

    past_date = (timezone.localdate() - timedelta(days=1)).strftime("%d/%m/%Y")
    data.update({"start_date": past_date, "end_date": past_date})
    response = admin_client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 302
    assert Event.objects.get().schedule_status == Event.ScheduleStatus.COMPLETED


@pytest.mark.django_db
def test_admin_saves_brazilian_date_and_full_24_hour_times(admin_client) -> None:
    data = event_data(published=False)
    data.pop("_event_date")
    data.pop("is_all_day")
    data.update(
        start_date="29/02/2032", end_date="29/02/2032", start_time="00:07", end_time="23:59"
    )

    response = admin_client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 302
    event = Event.objects.get()
    assert event.start_date == event.end_date == date(2032, 2, 29)
    assert event.start_time == time(0, 7)
    assert event.end_time == time(23, 59)
    content = admin_client.get(reverse("admin:events_event_change", args=[event.pk])).content
    assert b'name="start_time" value="00:07"' in content
    assert b'name="end_time" value="23:59"' in content


@pytest.mark.django_db
def test_admin_rejects_invalid_calendar_date_and_time(admin_client) -> None:
    data = event_data(published=False)
    data.pop("_event_date")
    data.pop("is_all_day")
    data.update(start_date="29/02/2027", start_time="24:00", end_time="12:60")

    response = admin_client.post(reverse("admin:events_event_add"), data)

    assert response.status_code == 200
    errors = response.context["adminform"].form.errors
    assert {"start_date", "start_time", "end_time"} <= errors.keys()
    assert not Event.objects.exists()
