from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import Query, Router

from apps.researchers.models import Researcher, ResearcherTranslation

from .models import Project, ProjectTranslation, project_situation_ordering
from .schemas import (
    Language,
    ProjectCover,
    ProjectDetail,
    ProjectLinks,
    ProjectListResponse,
    ProjectPerson,
    ProjectPersonPhoto,
    ProjectSummary,
    ProjectTranslationReference,
)

router = Router(tags=["projects"])


def serialize_cover(project: Project) -> ProjectCover | None:
    if not project.cover:
        return None
    return ProjectCover(url=project.cover.url, credit=project.cover_credit or None)


def serialize_person(researcher: Researcher, lang: Language) -> ProjectPerson:
    if not researcher.is_active:
        return ProjectPerson(name=researcher.full_name, slug=None, photo=None)

    translation = next(
        (item for item in researcher.translations.all() if item.language == lang and item.slug),
        None,
    )
    if translation is None:
        return ProjectPerson(name=researcher.full_name, slug=None, photo=None)

    photo = (
        ProjectPersonPhoto(url=researcher.photo.url, alt=researcher.full_name)
        if researcher.photo
        else None
    )
    return ProjectPerson(
        name=researcher.full_name,
        slug=translation.slug,
        photo=photo,
    )


def serialize_summary(
    translation: ProjectTranslation,
    lang: Language,
) -> ProjectSummary:
    project = translation.project
    if project.coordinator is None or project.start_date is None:
        raise RuntimeError("Projeto publicado sem coordenador ou data de início.")
    return ProjectSummary(
        slug=translation.slug or "",
        title=translation.title,
        summary=translation.summary,
        situation=project.situation,
        start_date=project.start_date,
        end_date=project.end_date,
        cover=serialize_cover(project),
        coordinator=serialize_person(project.coordinator, lang),
    )


def people_translation_prefetch() -> Prefetch:
    return Prefetch(
        "translations",
        queryset=ResearcherTranslation.objects.only("researcher_id", "language", "slug"),
    )


def project_queryset():
    return ProjectTranslation.objects.select_related(
        "project", "project__coordinator"
    ).prefetch_related(
        Prefetch(
            "project__coordinator__translations",
            queryset=ResearcherTranslation.objects.only("researcher_id", "language", "slug"),
        ),
        "project__translations",
    )


@router.get("", response=ProjectListResponse, summary="Lista projetos publicados")
def list_projects(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    featured: bool | None = None,
) -> ProjectListResponse:
    queryset = project_queryset().filter(
        language=lang,
        project__status=Project.Status.PUBLISHED,
        project__published_at__isnull=False,
    )
    if featured is not None:
        queryset = queryset.filter(project__is_featured=featured)

    situation_order = project_situation_ordering("project__situation")
    if featured is True:
        ordering = (
            "project__display_order",
            situation_order,
            "title",
            "project_id",
        )
    else:
        ordering = (
            situation_order,
            "project__display_order",
            "title",
            "project_id",
        )
    queryset = queryset.order_by(*ordering)

    total = queryset.count()
    start = (page - 1) * page_size
    items = [
        serialize_summary(translation, lang) for translation in queryset[start : start + page_size]
    ]
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response=ProjectDetail, summary="Obtém um projeto publicado")
def get_project(request, slug: str, lang: Language) -> ProjectDetail:
    translation = get_object_or_404(
        project_queryset().prefetch_related(
            Prefetch(
                "project__team",
                queryset=Researcher.objects.prefetch_related(people_translation_prefetch()),
            )
        ),
        language=lang,
        slug=slug,
        project__status=Project.Status.PUBLISHED,
        project__published_at__isnull=False,
    )
    project = translation.project
    summary = serialize_summary(translation, lang)
    references = [
        ProjectTranslationReference(lang=item.language, slug=item.slug or "")
        for item in project.translations.all()
        if item.slug
    ]
    partners = [line.strip() for line in project.partners.splitlines() if line.strip()]
    return ProjectDetail(
        **summary.model_dump(),
        body_html=translation.body_html,
        team=[serialize_person(person, lang) for person in project.team.all()],
        funding=project.funding or None,
        partners=partners,
        links=ProjectLinks(
            website=project.website_url or None,
            repository=project.repository_url or None,
        ),
        seo_title=translation.seo_title or translation.title,
        seo_description=translation.seo_description or translation.summary,
        translations=references,
    )
