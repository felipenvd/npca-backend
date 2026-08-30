from ninja import Query, Router

from .models import Course, CourseTranslation
from .schemas import CourseCover, CourseListResponse, CourseSummary, Language

router = Router(tags=["courses"])


def serialize_course(translation: CourseTranslation) -> CourseSummary:
    course = translation.course
    if not course.course_type or not course.external_url:
        raise RuntimeError("Curso publicado sem tipo ou URL externa.")
    return CourseSummary(
        id=course.pk,
        title=translation.title,
        summary=translation.summary,
        course_type=course.course_type,
        external_url=course.external_url,
        cover=(
            CourseCover(
                url=course.cover.url,
                alt=translation.cover_alt_text,
                credit=course.cover_credit or None,
            )
            if course.cover
            else None
        ),
        is_featured=course.is_featured,
    )


@router.get("", response=CourseListResponse, summary="Lista cursos e tutoriais")
def list_courses(
    request,
    lang: Language,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    featured: bool | None = Query(None),
) -> CourseListResponse:
    queryset = CourseTranslation.objects.select_related("course").filter(
        language=lang,
        course__status=Course.Status.PUBLISHED,
        course__published_at__isnull=False,
    )
    if featured is not None:
        queryset = queryset.filter(course__is_featured=featured)
    queryset = queryset.order_by(
        "-course__is_featured",
        "course__display_order",
        "title",
        "course_id",
    )
    total = queryset.count()
    start = (page - 1) * page_size
    items = [serialize_course(item) for item in queryset[start : start + page_size]]
    return CourseListResponse(items=items, total=total, page=page, page_size=page_size)
