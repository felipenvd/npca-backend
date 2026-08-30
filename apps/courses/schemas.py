from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]
CourseType = Literal[
    "channel",
    "course",
    "playlist",
    "tutorial",
    "recorded_live",
    "other",
]


class CourseCover(Schema):
    url: str
    alt: str
    credit: str | None


class CourseSummary(Schema):
    id: int
    title: str
    summary: str
    course_type: CourseType
    external_url: str
    cover: CourseCover | None
    is_featured: bool


class CourseListResponse(Schema):
    items: list[CourseSummary]
    total: int
    page: int
    page_size: int
