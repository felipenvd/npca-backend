from django.shortcuts import get_object_or_404
from ninja import Query, Router

from .models import ResearcherTranslation, academic_category_ordering
from .schemas import (
    Language,
    ResearcherDetail,
    ResearcherLinks,
    ResearcherListResponse,
    ResearcherPhoto,
    ResearcherSummary,
    ResearcherTranslationReference,
)

router = Router(tags=["researchers"])


def serialize_photo(translation: ResearcherTranslation) -> ResearcherPhoto | None:
    researcher = translation.researcher
    if not researcher.photo:
        return None
    return ResearcherPhoto(url=researcher.photo.url, alt=translation.photo_alt_text)


def serialize_summary(translation: ResearcherTranslation) -> ResearcherSummary:
    researcher = translation.researcher
    return ResearcherSummary(
        slug=translation.slug or "",
        name=researcher.full_name,
        academic_category=researcher.academic_category,
        role=translation.role,
        research_area=translation.research_area,
        photo=serialize_photo(translation),
    )


@router.get("", response=ResearcherListResponse, summary="Lista pesquisadores ativos")
def list_researchers(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=50),
) -> ResearcherListResponse:
    queryset = (
        ResearcherTranslation.objects.select_related("researcher")
        .filter(language=lang, researcher__is_active=True)
        .order_by(
            academic_category_ordering("researcher__academic_category"),
            "researcher__display_order",
            "researcher__full_name",
            "researcher_id",
        )
    )
    total = queryset.count()
    start = (page - 1) * page_size
    items = [serialize_summary(item) for item in queryset[start : start + page_size]]
    return ResearcherListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response=ResearcherDetail, summary="Obtém um pesquisador ativo")
def get_researcher(request, slug: str, lang: Language) -> ResearcherDetail:
    translation = get_object_or_404(
        ResearcherTranslation.objects.select_related("researcher").prefetch_related(
            "researcher__translations"
        ),
        language=lang,
        slug=slug,
        researcher__is_active=True,
    )
    researcher = translation.researcher
    summary = serialize_summary(translation)
    references = [
        ResearcherTranslationReference(lang=item.language, slug=item.slug or "")
        for item in researcher.translations.all()
        if item.slug
    ]
    seo_description = translation.seo_description or (
        f"{translation.role} — {translation.research_area}"
    )
    return ResearcherDetail(
        **summary.model_dump(),
        biography_html=translation.biography_html,
        email=researcher.public_email or None,
        links=ResearcherLinks(
            lattes=researcher.lattes_url or None,
            orcid=researcher.orcid_url or None,
            linkedin=researcher.linkedin_url or None,
        ),
        seo_title=translation.seo_title or researcher.full_name,
        seo_description=seo_description,
        translations=references,
    )
