import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.projects.models import Project, ProjectTranslation
from apps.publications.models import Publication, PublicationAuthor, PublicationTranslation
from apps.researchers.models import Researcher, ResearcherTranslation


def webp_upload() -> SimpleUploadedFile:
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("cover.webp", buffer.getvalue(), content_type="image/webp")


def create_researcher(name: str, *, active: bool = True) -> Researcher:
    researcher = Researcher.objects.create(
        full_name=name,
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=active,
    )
    for language in ("pt-br", "en"):
        ResearcherTranslation.objects.create(
            researcher=researcher,
            language=language,
            research_area="IA",
            biography_html="<p>Biografia</p>",
        )
    return researcher


def create_publication(
    *,
    title: str,
    year: int = 2026,
    order: int = 0,
    status: str = Publication.Status.PUBLISHED,
    document=None,
    cover=None,
    project: Project | None = None,
) -> Publication:
    publication = Publication.objects.create(
        status=status,
        year=year,
        venue="Simpósio de Computação Aplicada",
        doi="10.1000/example" if title == "Principal" else "",
        external_url="https://example.com/paper",
        document=document,
        cover=cover,
        cover_credit="NPCA" if cover else "",
        project=project,
        display_order=order,
    )
    PublicationTranslation.objects.create(
        publication=publication,
        language="pt-br",
        title=title,
        abstract=f"Resumo de {title}",
        cover_alt_text="Visualização da pesquisa" if cover else "",
    )
    PublicationTranslation.objects.create(
        publication=publication,
        language="en",
        title=f"{title} EN",
        abstract=f"Abstract of {title}",
        cover_alt_text="Research visualization" if cover else "",
    )
    PublicationAuthor.objects.create(
        publication=publication,
        researcher=create_researcher(f"Autora {title}"),
        display_order=1,
    )
    PublicationAuthor.objects.create(
        publication=publication,
        external_name="Colaborador Externo",
        display_order=2,
    )
    return publication


@pytest.mark.django_db
def test_list_requires_valid_language_and_pagination(client) -> None:
    assert client.get("/api/v1/publications").status_code == 422
    invalid = client.get("/api/v1/publications", {"lang": "fr"})
    excessive = client.get("/api/v1/publications", {"lang": "pt-br", "page_size": 51})

    assert invalid.status_code == 422
    assert excessive.status_code == 422
    assert invalid["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_list_only_published_orders_and_filters_by_year(client) -> None:
    create_publication(title="Mais recente B", order=2)
    create_publication(title="Mais recente A", order=1)
    create_publication(title="Anterior", year=2025)
    create_publication(title="Rascunho", status=Publication.Status.DRAFT)
    create_publication(title="Arquivada", status=Publication.Status.ARCHIVED)

    response = client.get("/api/v1/publications", {"lang": "pt-br", "page_size": 3})
    filtered = client.get("/api/v1/publications", {"lang": "pt-br", "year": 2025})

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert [item["title"] for item in response.json()["items"]] == [
        "Mais recente A",
        "Mais recente B",
        "Anterior",
    ]
    assert [item["title"] for item in filtered.json()["items"]] == ["Anterior"]


@pytest.mark.django_db
def test_detail_returns_authors_access_links_file_project_and_seo(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    project = Project.objects.create(
        status=Project.Status.PUBLISHED,
        start_date="2025-01-01",
        coordinator=create_researcher("Coordenadora"),
    )
    ProjectTranslation.objects.create(
        project=project,
        language="pt-br",
        title="Projeto relacionado",
        summary="Resumo",
        body_html="<p>Descrição</p>",
    )
    ProjectTranslation.objects.create(
        project=project,
        language="en",
        title="Related project",
        summary="Summary",
        body_html="<p>Description</p>",
    )
    publication = create_publication(
        title="Principal",
        project=project,
        cover=webp_upload(),
        document=SimpleUploadedFile(
            "paper.pdf",
            b"%PDF-1.7\ncontent",
            content_type="application/pdf",
        ),
    )

    response = client.get(f"/api/v1/publications/{publication.pk}", {"lang": "pt-br"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Principal"
    assert body["authors"][0]["slug"] == "autora-principal"
    assert body["authors"][1] == {
        "name": "Colaborador Externo",
        "slug": None,
        "photo": None,
    }
    assert body["doi"] == "10.1000/example"
    assert body["cover"] == {
        "url": f"/media/{publication.cover.name}",
        "alt": "Visualização da pesquisa",
        "credit": "NPCA",
    }
    assert body["file_url"] == f"/media/{publication.document.name}"
    assert body["project"] == {
        "id": project.pk,
        "title": "Projeto relacionado",
        "slug": "projeto-relacionado",
    }
    assert body["seo_title"] == "Principal"
    assert body["translations"] == [{"lang": "en"}, {"lang": "pt-br"}]


@pytest.mark.django_db
def test_detail_hides_unpublished_and_rejects_wrong_id(client) -> None:
    draft = create_publication(title="Rascunho", status=Publication.Status.DRAFT)

    hidden = client.get(f"/api/v1/publications/{draft.pk}", {"lang": "pt-br"})
    missing = client.get("/api/v1/publications/99999", {"lang": "pt-br"})

    assert hidden.status_code == 404
    assert missing.status_code == 404
    assert hidden["Content-Type"] == "application/problem+json"
