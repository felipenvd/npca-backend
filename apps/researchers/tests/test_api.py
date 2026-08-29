from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.researchers.models import Researcher, ResearcherTranslation


def create_active_researcher(
    *,
    name: str,
    order: int = 0,
    category: str = Researcher.AcademicCategory.DOCTOR,
    pt_slug: str | None = None,
    en_slug: str | None = None,
    photo=None,
) -> Researcher:
    researcher = Researcher.objects.create(
        full_name=name,
        academic_category=category,
        display_order=order,
        public_email="person@ufra.edu.br",
        lattes_url="http://lattes.cnpq.br/example",
        orcid_url="https://orcid.org/0000-0000-0000-0000",
        linkedin_url="https://linkedin.com/in/example",
        photo=photo,
    )
    ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
        slug=pt_slug,
        research_area="Inteligência Artificial",
        biography_html=f"<p>Biografia de {name}</p>",
    )
    ResearcherTranslation.objects.create(
        researcher=researcher,
        language="en",
        slug=en_slug,
        research_area="Artificial Intelligence",
        biography_html=f"<p>Biography of {name}</p>",
    )
    researcher.is_active = True
    researcher.save()
    return researcher


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("photo.webp", buffer.getvalue(), content_type="image/webp")


@pytest.mark.django_db
def test_list_requires_valid_language(client) -> None:
    missing = client.get("/api/v1/researchers")
    invalid = client.get("/api/v1/researchers", {"lang": "fr"})

    assert missing.status_code == 422
    assert invalid.status_code == 422
    assert missing["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_list_returns_only_active_researchers_in_requested_language(client) -> None:
    create_active_researcher(name="Ana Silva")
    inactive = Researcher.objects.create(
        full_name="Pessoa Inativa",
        academic_category=Researcher.AcademicCategory.DOCTORAL_STUDENT,
    )
    ResearcherTranslation.objects.create(
        researcher=inactive,
        language="pt-br",
    )

    response = client.get("/api/v1/researchers", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["name"] for item in response.json()["items"]] == ["Ana Silva"]
    assert response.json()["items"][0]["links"] == {
        "lattes": "http://lattes.cnpq.br/example",
        "orcid": "https://orcid.org/0000-0000-0000-0000",
        "linkedin": "https://linkedin.com/in/example",
    }


@pytest.mark.django_db
def test_list_is_paginated_and_ordered_by_category_then_display_order_and_name(client) -> None:
    create_active_researcher(
        name="Ana Mestranda",
        category=Researcher.AcademicCategory.MASTERS_STUDENT,
        order=1,
    )
    create_active_researcher(
        name="Carlos Mestre",
        category=Researcher.AcademicCategory.MASTER,
        order=1,
    )
    create_active_researcher(name="Bruno Doutor", order=2)
    create_active_researcher(name="Ana Doutora", order=1)

    first_page = client.get(
        "/api/v1/researchers",
        {"lang": "pt-br", "page": 1, "page_size": 2},
    )
    second_page = client.get(
        "/api/v1/researchers",
        {"lang": "pt-br", "page": 2, "page_size": 2},
    )

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 4
    assert [item["name"] for item in first_page.json()["items"]] == [
        "Ana Doutora",
        "Bruno Doutor",
    ]
    assert first_page.json()["items"][0]["academic_category"] == "doctor"
    assert [item["name"] for item in second_page.json()["items"]] == [
        "Carlos Mestre",
        "Ana Mestranda",
    ]


@pytest.mark.django_db
def test_detail_returns_links_seo_fallback_and_translation_slugs(client) -> None:
    create_active_researcher(
        name="Ana Silva",
        pt_slug="ana-silva",
        en_slug="ana-silva-en",
    )

    response = client.get("/api/v1/researchers/ana-silva", {"lang": "pt-br"})

    assert response.status_code == 200
    body = response.json()
    assert body["biography_html"] == "<p>Biografia de Ana Silva</p>"
    assert body["email"] == "person@ufra.edu.br"
    assert body["links"]["lattes"] == "http://lattes.cnpq.br/example"
    assert body["seo_title"] == "Ana Silva"
    assert body["seo_description"] == "Inteligência Artificial"
    assert "role" not in body
    assert body["translations"] == [
        {"lang": "en", "slug": "ana-silva-en"},
        {"lang": "pt-br", "slug": "ana-silva"},
    ]


@pytest.mark.django_db
def test_detail_hides_inactive_and_wrong_language_slugs(client) -> None:
    researcher = create_active_researcher(
        name="Ana Silva",
        pt_slug="ana-silva",
        en_slug="ana-silva-en",
    )

    wrong_language = client.get("/api/v1/researchers/ana-silva", {"lang": "en"})
    researcher.is_active = False
    researcher.save()
    inactive = client.get("/api/v1/researchers/ana-silva", {"lang": "pt-br"})

    assert wrong_language.status_code == 404
    assert inactive.status_code == 404
    assert inactive["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_photo_uses_relative_media_url(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    researcher = create_active_researcher(name="Ana Silva", photo=webp_upload())

    response = client.get("/api/v1/researchers/ana-silva", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json()["photo"] == {
        "url": f"/media/{researcher.photo.name}",
        "alt": "Ana Silva",
    }
