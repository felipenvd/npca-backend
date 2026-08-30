import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course


def course_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    return {
        "status": Course.Status.PUBLISHED if published else Course.Status.DRAFT,
        "course_type": Course.CourseType.COURSE if published else "",
        "external_url": "https://example.com/course" if published else "",
        "cover_credit": "",
        "is_featured": "on",
        "display_order": "0",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Introdução à IA",
        "translations-0-summary": "Fundamentos e aplicações.",
        "translations-0-cover_alt_text": "",
        "translations-1-language": "en",
        "translations-1-title": "Introduction to AI" if complete_english else "",
        "translations-1-summary": "Fundamentals and applications." if complete_english else "",
        "translations-1-cover_alt_text": "",
        "_save": "Salvar",
    }


@pytest.mark.django_db
def test_admin_exposes_external_link_translations_and_optional_cover(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:courses_course_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'value="pt-br" selected' in content
    assert 'value="en" selected' in content
    assert "URL externa *" in content
    assert "Imagem de divulgação" in content
    assert "Título *" in content
    assert "Resumo *" in content
    assert "upload de vídeo" not in content.lower()


@pytest.mark.django_db
def test_admin_allows_incomplete_draft_and_records_audit(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.post(reverse("admin:courses_course_add"), course_data(published=False))

    assert response.status_code == 302
    course = Course.objects.get()
    assert course.status == Course.Status.DRAFT
    assert course.created_by == admin_user
    assert course.updated_by == admin_user


@pytest.mark.django_db
def test_admin_blocks_incomplete_publication_and_accepts_complete_course(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = course_data(published=True)

    invalid = client.post(reverse("admin:courses_course_add"), data)

    assert invalid.status_code == 200
    assert not Course.objects.exists()

    data.update(
        {
            "translations-1-title": "Introduction to AI",
            "translations-1-summary": "Fundamentals and applications.",
        }
    )
    valid = client.post(reverse("admin:courses_course_add"), data)

    assert valid.status_code == 302
    course = Course.objects.get()
    assert course.status == Course.Status.PUBLISHED
    assert course.published_at is not None
    assert course.is_featured is True


@pytest.mark.django_db
def test_admin_rejects_http_url(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = course_data(published=False)
    data["external_url"] = "http://example.com/course"

    response = client.post(reverse("admin:courses_course_add"), data)

    assert response.status_code == 200
    assert not Course.objects.exists()
    assert "https://" in response.content.decode()
