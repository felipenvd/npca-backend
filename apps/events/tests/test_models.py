from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.events.models import Event, EventTranslation


def complete_translations(event: Event, *, with_location: bool = True) -> None:
    for language, title in (("pt-br", "Seminário Amazônia"), ("en", "Amazon Seminar")):
        EventTranslation.objects.create(
            event=event,
            language=language,
            title=title,
            summary="Resumo completo",
            body_html="<p>Descrição completa</p>",
            location_name="Auditório" if with_location else "",
        )


@pytest.mark.django_db
def test_incomplete_draft_can_be_saved() -> None:
    event = Event.objects.create()
    translation = EventTranslation.objects.create(event=event, language="pt-br")

    assert event.status == Event.Status.DRAFT
    assert event.start_date is None
    assert translation.slug is None


@pytest.mark.django_db
def test_translation_generates_stable_slug_sanitizes_html_and_enforces_uniqueness() -> None:
    event = Event.objects.create()
    translation = EventTranslation.objects.create(
        event=event,
        language="pt-br",
        title="Ciência na Amazônia",
        body_html='<p onclick="alert(1)">Texto</p><script>alert(1)</script>',
    )
    original_slug = translation.slug
    translation.title = "Novo título"
    translation.save()

    assert original_slug == "ciencia-na-amazonia"
    assert translation.slug == original_slug
    assert "onclick" not in translation.body_html
    assert "script" not in translation.body_html

    second = Event.objects.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        EventTranslation.objects.create(
            event=second,
            language="pt-br",
            title="Outro",
            slug=original_slug,
        )


@pytest.mark.django_db
def test_publication_requires_schedule_modality_urls_and_translations() -> None:
    event = Event.objects.create()
    with pytest.raises(ValidationError) as error:
        event.validate_for_publication()
    assert "tipo" in str(error.value)
    assert "modalidade" in str(error.value)
    assert "datas" in str(error.value)
    assert "Português" in str(error.value)
    assert "English" in str(error.value)

    event.event_type = Event.EventType.SEMINAR
    event.modality = Event.Modality.HYBRID
    event.start_date = date(2026, 9, 10)
    event.end_date = date(2026, 9, 10)
    event.is_all_day = True
    event.online_url = "https://meet.example.com/event"
    event.save()
    complete_translations(event)
    event.validate_for_publication()


@pytest.mark.django_db
def test_dates_times_and_all_day_rules_are_validated() -> None:
    event = Event(
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 9),
    )
    with pytest.raises(ValidationError, match="posterior"):
        event.full_clean()

    event.end_date = event.start_date
    event.start_time = time(10)
    event.end_time = time(9)
    with pytest.raises(ValidationError, match="término"):
        event.full_clean()

    event.is_all_day = True
    with pytest.raises(ValidationError, match="dia inteiro"):
        event.full_clean()


@pytest.mark.django_db
def test_temporal_state_uses_belem_timezone_and_exact_boundaries() -> None:
    event = Event.objects.create(
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 10),
        start_time=time(9),
        end_time=time(11),
    )
    belem = ZoneInfo("America/Belem")

    assert event.temporal_state(datetime(2026, 9, 10, 8, 59, tzinfo=belem)) == "upcoming"
    assert event.temporal_state(datetime(2026, 9, 10, 9, 0, tzinfo=belem)) == "ongoing"
    assert event.temporal_state(datetime(2026, 9, 10, 11, 0, tzinfo=belem)) == "past"

    event.is_all_day = True
    event.start_time = None
    event.end_time = None
    assert event.temporal_state(datetime(2026, 9, 10, 23, 59, tzinfo=belem)) == "ongoing"
    assert event.temporal_state(datetime(2026, 9, 11, 0, 0, tzinfo=belem)) == "past"


@pytest.mark.django_db
def test_first_publication_date_is_preserved() -> None:
    event = Event.objects.create(
        status=Event.Status.PUBLISHED,
        event_type=Event.EventType.LECTURE,
        modality=Event.Modality.ONLINE,
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 10),
        is_all_day=True,
        online_url="https://example.com/live",
    )
    first_publication = event.published_at
    event.status = Event.Status.ARCHIVED
    event.save()
    event.status = Event.Status.PUBLISHED
    event.save()

    assert first_publication is not None
    assert timezone.now() - first_publication < timedelta(seconds=2)
    assert event.published_at == first_publication
