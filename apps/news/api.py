from django.shortcuts import get_object_or_404
from ninja import Query, Router

from .models import News, NewsTranslation
from .schemas import (
    Language,
    NewsDetail,
    NewsImage,
    NewsListResponse,
    NewsSummary,
    NewsTranslationReference,
)

router = Router(tags=["news"])


def serialize_cover(translation: NewsTranslation) -> NewsImage | None:
    news = translation.news
    if not news.cover:
        return None
    return NewsImage(
        url=news.cover.url,
        alt=translation.cover_alt_text,
        credit=news.cover_credit,
    )


def serialize_summary(translation: NewsTranslation) -> NewsSummary:
    return NewsSummary(
        slug=translation.slug or "",
        title=translation.title,
        summary=translation.summary,
        published_at=translation.news.published_at,
        cover=serialize_cover(translation),
    )


@router.get("", response=NewsListResponse, summary="Lista notícias publicadas")
def list_news(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
) -> NewsListResponse:
    queryset = (
        NewsTranslation.objects.select_related("news")
        .filter(
            language=lang,
            news__status=News.Status.PUBLISHED,
            news__published_at__isnull=False,
        )
        .order_by("-news__published_at", "-news_id")
    )
    total = queryset.count()
    start = (page - 1) * page_size
    items = [serialize_summary(item) for item in queryset[start : start + page_size]]
    return NewsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response=NewsDetail, summary="Obtém uma notícia publicada")
def get_news(request, slug: str, lang: Language) -> NewsDetail:
    translation = get_object_or_404(
        NewsTranslation.objects.select_related("news").prefetch_related("news__translations"),
        language=lang,
        slug=slug,
        news__status=News.Status.PUBLISHED,
        news__published_at__isnull=False,
    )
    summary = serialize_summary(translation)
    references = [
        NewsTranslationReference(lang=item.language, slug=item.slug or "")
        for item in translation.news.translations.all()
        if item.slug
    ]
    return NewsDetail(
        **summary.model_dump(),
        body_html=translation.body_html,
        seo_title=translation.seo_title or translation.title,
        seo_description=translation.seo_description or translation.summary,
        translations=references,
    )
