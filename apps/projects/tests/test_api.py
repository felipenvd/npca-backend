from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.projects.models import Project, ProjectTeamMember, ProjectTranslation
from apps.researchers.models import Researcher, ResearcherTranslation


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("cover.webp", buffer.getvalue(), content_type="image/webp")


def create_researcher(name: str, *, active: bool = True, photo=None) -> Researcher:
    researcher = Researcher.objects.create(
        full_name=name,
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=active,
        photo=photo,
    )
    for language, area in (("pt-br", "IA"), ("en", "AI")):
        ResearcherTranslation.objects.create(
            researcher=researcher,
            language=language,
            research_area=area,
            biography_html="<p>Bio</p>",
        )
    return researcher


def create_project(
    *,
    title: str,
    situation: str = Project.Situation.ONGOING,
    order: int = 0,
    featured: bool = False,
    status: str = Project.Status.PUBLISHED,
    coordinator: Researcher | None = None,
    cover=None,
) -> Project:
    coordinator = coordinator or create_researcher(f"Coordenador {title}")
    project = Project.objects.create(
        status=status,
        situation=situation,
        coordinator=coordinator,
        start_date=date(2025, 1, 1),
        end_date=date(2026, 6, 1) if situation == Project.Situation.COMPLETED else None,
        display_order=order,
        is_featured=featured,
        funding="CNPq",
        partners="UFRA\nEmbrapa\n",
        website_url="https://example.com",
        repository_url="https://github.com/example/project",
        cover=cover,
    )
    ProjectTranslation.objects.create(
        project=project,
        language="pt-br",
        title=title,
        summary=f"Resumo de {title}",
        body_html="<p>Descrição</p>",
    )
    ProjectTranslation.objects.create(
        project=project,
        language="en",
        title=f"{title} EN",
        summary=f"Summary of {title}",
        body_html="<p>Description</p>",
    )
    return project


@pytest.mark.django_db
def test_list_requires_valid_language_and_pagination(client) -> None:
    assert client.get("/api/v1/projects").status_code == 422
    invalid = client.get("/api/v1/projects", {"lang": "fr"})
    excessive = client.get("/api/v1/projects", {"lang": "pt-br", "page_size": 51})

    assert invalid.status_code == 422
    assert excessive.status_code == 422
    assert invalid["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_list_only_published_and_orders_by_situation_then_manual_order(client) -> None:
    create_project(title="Concluído", situation=Project.Situation.COMPLETED)
    create_project(title="Planejado", situation=Project.Situation.PLANNED)
    create_project(title="Andamento B", order=2)
    create_project(title="Andamento A", order=1)
    create_project(title="Rascunho", status=Project.Status.DRAFT)
    create_project(title="Arquivado", status=Project.Status.ARCHIVED)

    response = client.get("/api/v1/projects", {"lang": "pt-br", "page": 1, "page_size": 3})

    assert response.status_code == 200
    assert response.json()["total"] == 4
    assert [item["title"] for item in response.json()["items"]] == [
        "Andamento A",
        "Andamento B",
        "Planejado",
    ]


@pytest.mark.django_db
def test_featured_filter_uses_manual_order_first(client) -> None:
    create_project(title="Em andamento", order=2, featured=True)
    create_project(
        title="Planejado",
        situation=Project.Situation.PLANNED,
        order=1,
        featured=True,
    )
    create_project(title="Não destacado", order=0)

    response = client.get(
        "/api/v1/projects",
        {"lang": "pt-br", "page_size": 3, "featured": "true"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [item["title"] for item in response.json()["items"]] == [
        "Planejado",
        "Em andamento",
    ]


@pytest.mark.django_db
def test_detail_returns_team_support_links_seo_and_translation_slugs(client) -> None:
    coordinator = create_researcher("Ana Coordenadora")
    active_member = create_researcher("Bruno Ativo")
    inactive_member = create_researcher("Carla Inativa", active=False)
    project = create_project(title="Amazônia", coordinator=coordinator)
    ProjectTeamMember.objects.create(project=project, researcher=active_member)
    ProjectTeamMember.objects.create(project=project, researcher=inactive_member)

    response = client.get("/api/v1/projects/amazonia", {"lang": "pt-br"})

    assert response.status_code == 200
    body = response.json()
    assert body["body_html"] == "<p>Descrição</p>"
    assert body["funding"] == "CNPq"
    assert body["partners"] == ["UFRA", "Embrapa"]
    assert body["links"] == {
        "website": "https://example.com",
        "repository": "https://github.com/example/project",
    }
    assert body["seo_title"] == "Amazônia"
    assert body["seo_description"] == "Resumo de Amazônia"
    assert body["coordinator"]["slug"] == "ana-coordenadora"
    assert body["team"][0]["slug"] == "bruno-ativo"
    assert body["team"][1] == {
        "name": "Carla Inativa",
        "slug": None,
        "photo": None,
    }
    assert body["translations"] == [
        {"lang": "en", "slug": "amazonia-en"},
        {"lang": "pt-br", "slug": "amazonia"},
    ]


@pytest.mark.django_db
def test_detail_hides_unpublished_and_wrong_language_slug(client) -> None:
    published = create_project(title="Publicado")
    draft = create_project(title="Rascunho", status=Project.Status.DRAFT)

    wrong_language = client.get("/api/v1/projects/publicado", {"lang": "en"})
    hidden = client.get(
        f"/api/v1/projects/{draft.translations.get(language='pt-br').slug}",
        {"lang": "pt-br"},
    )

    assert published.status == Project.Status.PUBLISHED
    assert wrong_language.status_code == 404
    assert hidden.status_code == 404
    assert hidden["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_cover_and_active_person_photo_use_relative_media_urls(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    coordinator = create_researcher("Ana Silva", photo=webp_upload())
    project = create_project(title="Com imagem", coordinator=coordinator, cover=webp_upload())

    response = client.get("/api/v1/projects/com-imagem", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json()["cover"]["url"] == f"/media/{project.cover.name}"
    assert response.json()["coordinator"]["photo"] == {
        "url": f"/media/{coordinator.photo.name}",
        "alt": "Ana Silva",
    }
