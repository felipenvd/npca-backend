from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]


class PublicationCover(Schema):
    url: str
    alt: str
    credit: str | None


class PublicationAuthorPhoto(Schema):
    url: str
    alt: str


class PublicationAuthorSchema(Schema):
    name: str
    slug: str | None
    photo: PublicationAuthorPhoto | None


class PublicationProject(Schema):
    id: int
    title: str
    slug: str


class PublicationSummary(Schema):
    id: int
    title: str
    abstract: str
    year: int
    venue: str
    authors: list[PublicationAuthorSchema]
    cover: PublicationCover | None
    doi: str | None
    external_url: str | None


class PublicationListResponse(Schema):
    items: list[PublicationSummary]
    total: int
    page: int
    page_size: int


class PublicationTranslationReference(Schema):
    lang: Language


class PublicationDetail(PublicationSummary):
    file_url: str | None
    project: PublicationProject | None
    seo_title: str
    seo_description: str
    translations: list[PublicationTranslationReference]
