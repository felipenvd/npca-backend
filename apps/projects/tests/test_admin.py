import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.projects.models import Project
from apps.researchers.models import Researcher


def project_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    return {
        "status": Project.Status.PUBLISHED if published else Project.Status.DRAFT,
        "situation": Project.Situation.ONGOING,
        "coordinator": "",
        "start_date": "",
        "end_date": "",
        "cover_credit": "",
        "funding": "",
        "partners": "",
        "website_url": "",
        "repository_url": "",
        "display_order": "0",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Projeto Amazônia",
        "translations-0-slug": "",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Descrição</p>",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-title": "Amazon Project" if complete_english else "",
        "translations-1-slug": "",
        "translations-1-summary": "Summary" if complete_english else "",
        "translations-1-body_html": "<p>Description</p>" if complete_english else "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "team_memberships-TOTAL_FORMS": "1",
        "team_memberships-INITIAL_FORMS": "0",
        "team_memberships-MIN_NUM_FORMS": "0",
        "team_memberships-MAX_NUM_FORMS": "1000",
        "team_memberships-0-researcher": "",
        "_save": "Salvar",
    }


@pytest.mark.django_db
def test_admin_add_page_exposes_editorial_fields_and_two_languages(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:projects_project_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "unfold/forms/js/trix/trix.js" in content
    assert 'value="pt-br" selected' in content
    assert 'value="en" selected' in content
    assert "Título *" in content
    assert "Resumo *" in content
    assert "Descrição *" in content
    assert "Coordenador *" in content
    assert "Data de início *" in content
    assert content.count('type="date"') == 2
    assert "vDateField" not in content
    assert "Gerado automaticamente a partir do título" in content
    assert "Texto alternativo" not in content
    assert "Site do projeto" in content
    assert "Repositório" in content


@pytest.mark.django_db
def test_admin_allows_incomplete_draft_and_records_audit(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:projects_project_add"),
        project_data(published=False),
    )

    assert response.status_code == 302
    project = Project.objects.get()
    assert project.created_by == admin_user
    assert project.updated_by == admin_user
    assert project.translations.get(language="pt-br").slug == "projeto-amazonia"


@pytest.mark.django_db
def test_admin_blocks_incomplete_publication_and_accepts_complete_project(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    coordinator = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    client.force_login(admin_user)
    data = project_data(published=True)

    invalid_response = client.post(reverse("admin:projects_project_add"), data)

    assert invalid_response.status_code == 200
    assert not Project.objects.exists()

    data.update(
        {
            "coordinator": str(coordinator.pk),
            "start_date": "2026-01-01",
            "translations-1-title": "Amazon Project",
            "translations-1-summary": "Summary",
            "translations-1-body_html": "<p>Description</p>",
        }
    )
    valid_response = client.post(reverse("admin:projects_project_add"), data)

    assert valid_response.status_code == 302
    project = Project.objects.get()
    assert project.status == Project.Status.PUBLISHED
    assert project.published_at is not None


@pytest.mark.django_db
def test_admin_blocks_coordinator_in_team(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    coordinator = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    client.force_login(admin_user)
    data = project_data(published=False)
    data["coordinator"] = str(coordinator.pk)
    data["team_memberships-0-researcher"] = str(coordinator.pk)

    response = client.post(reverse("admin:projects_project_add"), data)

    assert response.status_code == 200
    assert not Project.objects.exists()
    assert "não pode aparecer também na equipe" in response.content.decode()
