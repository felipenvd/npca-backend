from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.courses.models import Course, CourseTranslation


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("course.webp", buffer.getvalue(), content_type="image/webp")


def create_course(
    *,
    title: str,
    featured: bool = False,
    order: int = 0,
    status: str = Course.Status.PUBLISHED,
    cover=None,
    include_english: bool = True,
) -> Course:
    course = Course.objects.create(
        status=status,
        course_type=Course.CourseType.COURSE,
        external_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        cover=cover,
        cover_credit="NPCA" if cover else "",
        is_featured=featured,
        display_order=order,
    )
    CourseTranslation.objects.create(
        course=course,
        language="pt-br",
        title=title,
        summary=f"Resumo de {title}",
        cover_alt_text="Pessoa ministrando uma aula" if cover else "",
    )
    if include_english:
        CourseTranslation.objects.create(
            course=course,
            language="en",
            title=f"{title} EN",
            summary=f"Summary of {title}",
            cover_alt_text="Person teaching a class" if cover else "",
        )
    return course


@pytest.mark.django_db
def test_list_requires_valid_language_and_pagination(client) -> None:
    assert client.get("/api/v1/courses").status_code == 422
    assert client.get("/api/v1/courses", {"lang": "fr"}).status_code == 422
    assert client.get("/api/v1/courses", {"lang": "pt-br", "page_size": 51}).status_code == 422


@pytest.mark.django_db
def test_list_hides_drafts_orders_featured_and_filters(client) -> None:
    create_course(title="Comum", order=0)
    create_course(title="Destaque B", featured=True, order=2)
    create_course(title="Destaque A", featured=True, order=1)
    create_course(title="Rascunho", status=Course.Status.DRAFT)

    response = client.get("/api/v1/courses", {"lang": "pt-br", "page_size": 10})
    featured = client.get(
        "/api/v1/courses",
        {"lang": "pt-br", "featured": "true", "page_size": 4},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert [item["title"] for item in response.json()["items"]] == [
        "Destaque A",
        "Destaque B",
        "Comum",
    ]
    assert [item["title"] for item in featured.json()["items"]] == [
        "Destaque A",
        "Destaque B",
    ]


@pytest.mark.django_db
def test_list_localizes_content_and_returns_relative_cover(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    course = create_course(title="Curso", featured=True, cover=webp_upload())

    response = client.get("/api/v1/courses", {"lang": "en"})

    assert response.status_code == 200
    assert course.cover.name.startswith("courses/covers/")
    assert course.cover.name.endswith(".webp")
    assert course.cover.name != "courses/covers/course.webp"
    assert response.json()["items"] == [
        {
            "id": course.pk,
            "title": "Curso EN",
            "summary": "Summary of Curso",
            "course_type": "course",
            "external_url": "https://example.com/curso",
            "cover": {
                "url": f"/media/{course.cover.name}",
                "alt": "Person teaching a class",
                "credit": "NPCA",
            },
            "is_featured": True,
        }
    ]


@pytest.mark.django_db
def test_requested_language_without_translation_is_hidden(client) -> None:
    create_course(title="Somente português", include_english=False)

    response = client.get("/api/v1/courses", {"lang": "en"})

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.django_db
def test_list_paginates_results(client) -> None:
    for index in range(3):
        create_course(title=f"Curso {index}", order=index)

    response = client.get(
        "/api/v1/courses",
        {"lang": "pt-br", "page": 2, "page_size": 2},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 2
    assert [item["title"] for item in response.json()["items"]] == ["Curso 2"]
