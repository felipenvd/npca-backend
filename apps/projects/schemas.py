from datetime import date
from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]
ProjectSituation = Literal["planned", "ongoing", "completed"]


class ProjectCover(Schema):
    url: str
    credit: str | None


class ProjectPersonPhoto(Schema):
    url: str
    alt: str


class ProjectPerson(Schema):
    name: str
    slug: str | None
    photo: ProjectPersonPhoto | None


class ProjectSummary(Schema):
    slug: str
    title: str
    summary: str
    situation: ProjectSituation
    start_date: date
    end_date: date | None
    cover: ProjectCover | None
    coordinator: ProjectPerson


class ProjectListResponse(Schema):
    items: list[ProjectSummary]
    total: int
    page: int
    page_size: int


class ProjectLinks(Schema):
    website: str | None
    repository: str | None


class ProjectTranslationReference(Schema):
    lang: Language
    slug: str


class ProjectDetail(ProjectSummary):
    body_html: str
    team: list[ProjectPerson]
    funding: str | None
    partners: list[str]
    links: ProjectLinks
    seo_title: str
    seo_description: str
    translations: list[ProjectTranslationReference]
