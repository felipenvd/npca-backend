from datetime import datetime
from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]


class NewsImage(Schema):
    url: str
    credit: str


class NewsSummary(Schema):
    slug: str
    title: str
    summary: str
    published_at: datetime
    cover: NewsImage | None


class NewsListResponse(Schema):
    items: list[NewsSummary]
    total: int
    page: int
    page_size: int


class NewsTranslationReference(Schema):
    lang: Language
    slug: str


class NewsDetail(NewsSummary):
    body_html: str
    seo_title: str
    seo_description: str
    translations: list[NewsTranslationReference]
