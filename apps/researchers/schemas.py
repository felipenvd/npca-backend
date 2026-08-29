from typing import Literal

from ninja import Schema

Language = Literal["pt-br", "en"]
AcademicCategory = Literal[
    "doctor",
    "doctoral_student",
    "masters_student",
    "undergraduate_researcher",
]


class ResearcherPhoto(Schema):
    url: str
    alt: str


class ResearcherSummary(Schema):
    slug: str
    name: str
    academic_category: AcademicCategory
    role: str
    research_area: str
    photo: ResearcherPhoto | None


class ResearcherListResponse(Schema):
    items: list[ResearcherSummary]
    total: int
    page: int
    page_size: int


class ResearcherLinks(Schema):
    lattes: str | None
    orcid: str | None
    linkedin: str | None


class ResearcherTranslationReference(Schema):
    lang: Language
    slug: str


class ResearcherDetail(ResearcherSummary):
    biography_html: str
    email: str | None
    links: ResearcherLinks
    seo_title: str
    seo_description: str
    translations: list[ResearcherTranslationReference]
