from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import Query, Router

from apps.projects.models import Project, ProjectTranslation
from apps.researchers.models import ResearcherTranslation

from .models import Publication, PublicationAuthor, PublicationTranslation
from .schemas import (
    Language,
    PublicationAuthorPhoto,
    PublicationAuthorSchema,
    PublicationDetail,
    PublicationListResponse,
    PublicationProject,
    PublicationSummary,
    PublicationTranslationReference,
)

router = Router(tags=["publications"])


def serialize_author(author: PublicationAuthor, lang: Language) -> PublicationAuthorSchema:
    if author.researcher is None:
        return PublicationAuthorSchema(name=author.external_name, slug=None, photo=None)

    researcher = author.researcher
    if not researcher.is_active:
        return PublicationAuthorSchema(name=researcher.full_name, slug=None, photo=None)
    translation = next(
        (item for item in researcher.translations.all() if item.language == lang and item.slug),
        None,
    )
    if translation is None:
        return PublicationAuthorSchema(name=researcher.full_name, slug=None, photo=None)
    photo = (
        PublicationAuthorPhoto(url=researcher.photo.url, alt=researcher.full_name)
        if researcher.photo
        else None
    )
    return PublicationAuthorSchema(name=researcher.full_name, slug=translation.slug, photo=photo)


def serialize_summary(
    translation: PublicationTranslation,
    lang: Language,
) -> PublicationSummary:
    publication = translation.publication
    if publication.year is None:
        raise RuntimeError("Publicação publicada sem ano.")
    return PublicationSummary(
        id=publication.pk,
        title=translation.title,
        abstract=translation.abstract,
        year=publication.year,
        venue=publication.venue,
        authors=[serialize_author(author, lang) for author in publication.author_records.all()],
        doi=publication.doi or None,
        external_url=publication.external_url or None,
    )


def publication_queryset():
    author_queryset = PublicationAuthor.objects.select_related("researcher").prefetch_related(
        Prefetch(
            "researcher__translations",
            queryset=ResearcherTranslation.objects.only("researcher_id", "language", "slug"),
        )
    )
    return PublicationTranslation.objects.select_related(
        "publication",
        "publication__project",
    ).prefetch_related(
        Prefetch("publication__author_records", queryset=author_queryset),
        "publication__translations",
        Prefetch(
            "publication__project__translations",
            queryset=ProjectTranslation.objects.only("project_id", "language", "title", "slug"),
        ),
    )


@router.get("", response=PublicationListResponse, summary="Lista publicações")
def list_publications(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    year: int | None = Query(None, ge=1000),
) -> PublicationListResponse:
    queryset = publication_queryset().filter(
        language=lang,
        publication__status=Publication.Status.PUBLISHED,
        publication__published_at__isnull=False,
    )
    if year is not None:
        queryset = queryset.filter(publication__year=year)
    queryset = queryset.order_by(
        "-publication__year",
        "publication__display_order",
        "title",
        "publication_id",
    )
    total = queryset.count()
    start = (page - 1) * page_size
    items = [
        serialize_summary(translation, lang) for translation in queryset[start : start + page_size]
    ]
    return PublicationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{publication_id}", response=PublicationDetail, summary="Obtém uma publicação")
def get_publication(request, publication_id: int, lang: Language) -> PublicationDetail:
    translation = get_object_or_404(
        publication_queryset(),
        publication_id=publication_id,
        language=lang,
        publication__status=Publication.Status.PUBLISHED,
        publication__published_at__isnull=False,
    )
    publication = translation.publication
    summary = serialize_summary(translation, lang)
    project_reference = None
    project = publication.project
    if project and project.status == Project.Status.PUBLISHED and project.published_at:
        project_translation = next(
            (
                item
                for item in project.translations.all()
                if item.language == lang and item.title and item.slug
            ),
            None,
        )
        if project_translation:
            project_reference = PublicationProject(
                id=project.pk,
                title=project_translation.title,
                slug=project_translation.slug or "",
            )
    return PublicationDetail(
        **summary.model_dump(),
        file_url=publication.document.url if publication.document else None,
        project=project_reference,
        seo_title=translation.seo_title or translation.title,
        seo_description=translation.seo_description or translation.abstract[:160],
        translations=[
            PublicationTranslationReference(lang=item.language)
            for item in publication.translations.all()
            if item.title and item.abstract
        ],
    )
