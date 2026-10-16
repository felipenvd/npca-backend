from datetime import date, datetime, time, timedelta
from unittest.mock import patch
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
def test_publication_requires_schedule_modality_and_translations() -> None:
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
@pytest.mark.parametrize("modality", [Event.Modality.ONLINE, Event.Modality.HYBRID])
def test_online_and_hybrid_events_can_be_published_without_access_url(modality) -> None:
    event = Event(
        status=Event.Status.PUBLISHED,
        event_type=Event.EventType.COURSE,
        modality=modality,
        start_date=date(2025, 4, 12),
        end_date=date(2025, 7, 5),
        start_time=time(15),
        end_time=time(18),
        online_url="",
    )
    event.full_clean()
    event.save()
    complete_translations(event, with_location=modality == Event.Modality.HYBRID)
    event.validate_for_publication()
    event.refresh_from_db()
    assert event.online_url == ""
    assert event.published_at is not None


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


@pytest.mark.django_db
@pytest.mark.parametrize("hour", (8, 9, 10, 11))
def test_completed_status_requires_end_time_and_allows_exact_boundary(hour) -> None:
    event = Event.objects.create(
        schedule_status=Event.ScheduleStatus.COMPLETED,
        event_type=Event.EventType.SEMINAR,
        modality=Event.Modality.IN_PERSON,
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 10),
        start_time=time(9),
        end_time=time(11),
    )
    complete_translations(event)
    reference = datetime(2026, 9, 10, hour, tzinfo=ZoneInfo("America/Belem"))

    with patch("apps.events.models.timezone.now", return_value=reference):
        if hour < 11:
            with pytest.raises(ValidationError, match="após o término"):
                event.full_clean()
            with pytest.raises(ValidationError, match="após o término"):
                event.validate_for_publication()
        else:
            event.full_clean()
            event.validate_for_publication()
            assert event.temporal_state() == "past"


@pytest.mark.django_db
def test_completed_all_day_requires_day_to_end_and_does_not_mark_other_events() -> None:
    event = Event(
        schedule_status=Event.ScheduleStatus.COMPLETED,
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 10),
        is_all_day=True,
    )
    belem = ZoneInfo("America/Belem")
    with patch(
        "apps.events.models.timezone.now", return_value=datetime(2026, 9, 10, 23, 59, tzinfo=belem)
    ):
        with pytest.raises(ValidationError, match="após o término"):
            event.full_clean()
    with patch("apps.events.models.timezone.now", return_value=datetime(2026, 9, 11, tzinfo=belem)):
        event.full_clean()
        event.schedule_status = Event.ScheduleStatus.SCHEDULED
        event.full_clean()
        assert event.temporal_state() == "past"
        assert event.schedule_status == "scheduled"


@pytest.mark.django_db
def test_completed_draft_requires_dates_but_not_times() -> None:
    event = Event(schedule_status=Event.ScheduleStatus.COMPLETED)

    with pytest.raises(ValidationError, match="Informe as datas"):
        event.full_clean()

    event.start_date = event.end_date = timezone.localdate() - timedelta(days=1)
    event.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("start_time", "end_time", "states"),
    [
        (None, None, ["ongoing", "ongoing", "ongoing", "ongoing", "ongoing"]),
        (time(9), None, ["upcoming", "ongoing", "ongoing", "ongoing", "ongoing"]),
        (None, time(11), ["ongoing", "ongoing", "ongoing", "past", "past"]),
        (time(9), time(11), ["upcoming", "ongoing", "ongoing", "past", "past"]),
    ],
)
def test_optional_times_define_independent_temporal_boundaries_and_completion(
    start_time, end_time, states
):
    event = Event.objects.create(
        status=Event.Status.PUBLISHED,
        event_type=Event.EventType.CONFERENCE,
        modality=Event.Modality.IN_PERSON,
        start_date=date(2025, 7, 20),
        end_date=date(2025, 7, 20),
        start_time=start_time,
        end_time=end_time,
    )
    complete_translations(event)
    event.full_clean()
    event.validate_for_publication()
    event.schedule_status = Event.ScheduleStatus.COMPLETED
    belem = ZoneInfo("America/Belem")
    for hour, expected in zip([8, 9, 10, 11, 23], states, strict=True):
        reference = datetime(2025, 7, 20, hour, tzinfo=belem)
        with patch("apps.events.models.timezone.now", return_value=reference):
            assert event.temporal_state() == expected
            if expected == "past":
                event.full_clean()
                event.validate_for_publication()
            else:
                with pytest.raises(ValidationError, match="após o término"):
                    event.full_clean()
                with pytest.raises(ValidationError, match="após o término"):
                    event.validate_for_publication()
    assert event.temporal_state(datetime(2025, 7, 19, 23, 59, tzinfo=belem)) == "upcoming"
    with patch("apps.events.models.timezone.now", return_value=datetime(2025, 7, 21, tzinfo=belem)):
        assert event.temporal_state() == "past"
        event.full_clean()
        event.validate_for_publication()
