from datetime import datetime

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Query, Router

from .models import Event, EventTranslation
from .schemas import (
    EventCover,
    EventDetail,
    EventListResponse,
    EventLocation,
    EventPeriod,
    EventSummary,
    EventTranslationReference,
    EventType,
    Language,
)

router = Router(tags=["events"])


def serialize_summary(
    translation: EventTranslation,
    *,
    reference: datetime | None = None,
) -> EventSummary:
    event = translation.event
    if event.start_date is None or event.end_date is None:
        raise RuntimeError("Evento publicado sem datas completas.")
    return EventSummary(
        slug=translation.slug or "",
        title=translation.title,
        summary=translation.summary,
        event_type=event.event_type,
        schedule_status=event.schedule_status,
        temporal_state=event.temporal_state(reference),
        start_date=event.start_date,
        end_date=event.end_date,
        is_all_day=event.is_all_day,
        start_time=event.start_time,
        end_time=event.end_time,
        cover=(
            EventCover(
                url=event.cover.url,
                alt=translation.cover_alt_text,
                credit=event.cover_credit or None,
            )
            if event.cover
            else None
        ),
        location=EventLocation(
            modality=event.modality,
            name=translation.location_name or None,
            address=translation.location_address or None,
            online_url=event.online_url or None,
        ),
    )


def event_queryset():
    return EventTranslation.objects.select_related("event").prefetch_related("event__translations")


def temporal_conditions(reference: datetime) -> tuple[Q, Q, Q]:
    local_reference = timezone.localtime(reference)
    today = local_reference.date()
    current_time = local_reference.time().replace(tzinfo=None)
    upcoming = (
        Q(event__end_date__gt=today)
        | Q(event__end_date=today, event__is_all_day=True)
        | Q(
            event__end_date=today,
            event__is_all_day=False,
            event__end_time__gt=current_time,
        )
    )
    started = (
        Q(event__start_date__lt=today)
        | Q(event__start_date=today, event__is_all_day=True)
        | Q(
            event__start_date=today,
            event__is_all_day=False,
            event__start_time__lte=current_time,
        )
    )
    ongoing = upcoming & started
    past = Q(event__end_date__lt=today) | Q(
        event__end_date=today,
        event__is_all_day=False,
        event__end_time__lte=current_time,
    )
    return upcoming, ongoing, past


@router.get("", response=EventListResponse, summary="Lista eventos publicados")
def list_events(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    period: EventPeriod = "upcoming",
    type: EventType | None = None,
    include_canceled: bool = True,
) -> EventListResponse:
    reference = timezone.now()
    upcoming, ongoing, past = temporal_conditions(reference)
    queryset = event_queryset().filter(
        language=lang,
        event__status=Event.Status.PUBLISHED,
        event__published_at__isnull=False,
    )
    if period == "upcoming":
        queryset = queryset.filter(upcoming).annotate(
            temporal_priority=Case(
                When(ongoing, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        ordering = (
            "temporal_priority",
            "event__start_date",
            F("event__start_time").asc(nulls_first=True),
            "event__display_order",
            "title",
            "event_id",
        )
    elif period == "past":
        queryset = queryset.filter(past)
        ordering = (
            "-event__end_date",
            F("event__end_time").desc(nulls_last=True),
            "event__display_order",
            "title",
            "event_id",
        )
    else:
        ordering = (
            "-event__start_date",
            F("event__start_time").desc(nulls_last=True),
            "event__display_order",
            "title",
            "event_id",
        )
    if type is not None:
        queryset = queryset.filter(event__event_type=type)
    if not include_canceled:
        queryset = queryset.exclude(event__schedule_status=Event.ScheduleStatus.CANCELED)
    queryset = queryset.order_by(*ordering)

    total = queryset.count()
    start = (page - 1) * page_size
    items = [
        serialize_summary(translation, reference=reference)
        for translation in queryset[start : start + page_size]
    ]
    return EventListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response=EventDetail, summary="Obtém um evento publicado")
def get_event(request, slug: str, lang: Language) -> EventDetail:
    reference = timezone.now()
    translation = get_object_or_404(
        event_queryset(),
        language=lang,
        slug=slug,
        event__status=Event.Status.PUBLISHED,
        event__published_at__isnull=False,
    )
    event = translation.event
    summary = serialize_summary(translation, reference=reference)
    return EventDetail(
        **summary.model_dump(),
        body_html=translation.body_html,
        registration_url=event.registration_url or None,
        seo_title=translation.seo_title or translation.title,
        seo_description=translation.seo_description or translation.summary,
        translations=[
            EventTranslationReference(lang=item.language, slug=item.slug or "")
            for item in event.translations.all()
            if item.slug
        ],
    )
