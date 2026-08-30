from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.courses.models import Course, CourseTranslation


def complete_translations(course: Course) -> None:
    CourseTranslation.objects.create(
        course=course,
        language="pt-br",
        title="Introdução à IA",
        summary="Fundamentos e aplicações.",
    )
    CourseTranslation.objects.create(
        course=course,
        language="en",
        title="Introduction to AI",
        summary="Fundamentals and applications.",
    )


@pytest.mark.django_db
def test_incomplete_draft_can_be_saved() -> None:
    course = Course.objects.create()
    translation = CourseTranslation.objects.create(course=course, language="pt-br")

    assert course.status == Course.Status.DRAFT
    assert course.external_url == ""
    assert translation.title == ""


@pytest.mark.django_db
def test_url_must_be_https_even_in_draft() -> None:
    course = Course(
        course_type=Course.CourseType.COURSE,
        external_url="http://example.com/course",
    )

    with pytest.raises(ValidationError, match="https://"):
        course.full_clean()


@pytest.mark.django_db
def test_publication_requires_type_url_and_bilingual_content() -> None:
    course = Course.objects.create()

    with pytest.raises(ValidationError) as error:
        course.validate_for_publication()

    assert "tipo" in str(error.value)
    assert "URL" in str(error.value)
    assert "Português" in str(error.value)
    assert "English" in str(error.value)

    course.course_type = Course.CourseType.COURSE
    course.external_url = "https://example.com/course"
    course.save()
    complete_translations(course)
    course.validate_for_publication()


@pytest.mark.django_db
def test_first_publication_date_is_preserved() -> None:
    course = Course.objects.create(
        status=Course.Status.PUBLISHED,
        course_type=Course.CourseType.PLAYLIST,
        external_url="https://example.com/playlist",
    )
    first_publication = course.published_at
    course.status = Course.Status.ARCHIVED
    course.save()
    course.status = Course.Status.DRAFT
    course.save()
    course.status = Course.Status.PUBLISHED
    course.save()

    assert first_publication is not None
    assert timezone.now() - first_publication < timedelta(seconds=2)
    assert course.published_at == first_publication
