from datetime import date, time
from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]
EventPeriod = Literal["upcoming", "past", "all"]
EventType = Literal[
    "lecture",
    "seminar",
    "workshop",
    "course",
    "defense",
    "conference",
    "meetup",
    "other",
]
ScheduleStatus = Literal["scheduled", "postponed", "canceled"]
TemporalState = Literal["upcoming", "ongoing", "past"]
Modality = Literal["in_person", "online", "hybrid"]


class EventCover(Schema):
    url: str
    alt: str
    credit: str | None


class EventLocation(Schema):
    modality: Modality
    name: str | None
    address: str | None
    online_url: str | None


class EventSummary(Schema):
    slug: str
    title: str
    summary: str
    event_type: EventType
    schedule_status: ScheduleStatus
    temporal_state: TemporalState
    start_date: date
    end_date: date
    is_all_day: bool
    start_time: time | None
    end_time: time | None
    cover: EventCover | None
    location: EventLocation


class EventListResponse(Schema):
    items: list[EventSummary]
    total: int
    page: int
    page_size: int


class EventTranslationReference(Schema):
    lang: Language
    slug: str


class EventDetail(EventSummary):
    body_html: str
    registration_url: str | None
    seo_title: str
    seo_description: str
    translations: list[EventTranslationReference]
