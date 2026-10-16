import pytest
from django.urls import reverse
from django.utils.html import strip_tags

from apps.accounts.models import User
from apps.projects.models import Project
from apps.researchers.models import Researcher


def project_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    return {
        "status": Project.Status.PUBLISHED if published else Project.Status.DRAFT,
        "situation": Project.Situation.ONGOING,
        "coordinator": "",
        "start_year": "",
        "end_year": "",
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
        "team_memberships-0-external_name": "",
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
    assert 'name="translations-0-language" value="pt-br"' in content
    assert 'name="translations-1-language" value="en"' in content
    assert "Título *" in strip_tags(content)
    assert "Resumo *" in strip_tags(content)
    assert "Descrição *" in strip_tags(content)
    assert "Coordenador *" in strip_tags(content)
    assert "Ano de início *" in strip_tags(content)
    assert "Ano de término" in strip_tags(content)
    assert 'name="start_year"' in content
    assert 'name="end_year"' in content
    assert 'name="start_date"' not in content
    assert 'name="end_date"' not in content
    assert "npca-enhanced-date-field" not in content
    assert "Gerado automaticamente a partir do título" in content
    assert "Texto alternativo" not in content
    assert "Site do projeto" in content
    assert "Repositório" in content
    assert "Pesquisador cadastrado" in content
    assert "Nome do integrante externo" in content


@pytest.mark.django_db
def test_admin_saves_mixed_team_and_can_change_a_member_to_external(admin_client):
    from apps.core.tests.test_bilingual_admin import FormValues

    researcher = Researcher.objects.create(
        full_name="Integrante NPCA", academic_category=Researcher.AcademicCategory.DOCTOR
    )
    data = project_data(published=False)
    data.update(
        {
            "team_memberships-TOTAL_FORMS": "3",
            "team_memberships-0-researcher": str(researcher.pk),
            "team_memberships-1-researcher": "",
            "team_memberships-1-external_name": "Colaboradora externa",
            "team_memberships-2-researcher": "",
            "team_memberships-2-external_name": "",
        }
    )

    response = admin_client.post(reverse("admin:projects_project_add"), data)

    assert response.status_code == 302
    project = Project.objects.get()
    assert project.team_memberships.count() == 2
    assert project.team_memberships.get(researcher=None).external_name == "Colaboradora externa"
    url = reverse("admin:projects_project_change", args=[project.pk])
    page = admin_client.get(url)
    values = FormValues(page.content.decode(), "project_form").values
    values.update(
        {
            "team_memberships-0-researcher": "",
            "team_memberships-0-external_name": "Outro colaborador externo",
            "_save": "Salvar",
        }
    )

    updated = admin_client.post(url, values)

    assert updated.status_code == 302
    assert not project.team.exists()
    assert project.team_memberships.count() == 2
    assert Researcher.objects.count() == 1


@pytest.mark.django_db
def test_admin_rejects_both_member_identities(admin_client):
    researcher = Researcher.objects.create(
        full_name="Integrante NPCA", academic_category=Researcher.AcademicCategory.DOCTOR
    )
    data = project_data(published=False)
    data["team_memberships-0-researcher"] = str(researcher.pk)
    data["team_memberships-0-external_name"] = "Colaborador externo"

    response = admin_client.post(reverse("admin:projects_project_add"), data)

    assert response.status_code == 200
    assert "nunca ambos" in response.content.decode()
    assert not Project.objects.exists()


@pytest.mark.django_db
def test_admin_rejects_duplicate_external_members(admin_client):
    data = project_data(published=False)
    data.update(
        {
            "team_memberships-TOTAL_FORMS": "2",
            "team_memberships-0-external_name": "Colaboradora externa",
            "team_memberships-1-external_name": "colaboradora externa",
        }
    )

    response = admin_client.post(reverse("admin:projects_project_add"), data)

    assert response.status_code == 200
    assert "Cada integrante externo deve aparecer apenas uma vez" in response.content.decode()
    assert not Project.objects.exists()


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
            "start_year": "2026",
            "translations-1-title": "Amazon Project",
            "translations-1-summary": "Summary",
            "translations-1-body_html": "<p>Description</p>",
        }
    )
    valid_response = client.post(reverse("admin:projects_project_add"), data)

    assert valid_response.status_code == 302
    project = Project.objects.get()
    assert project.status == Project.Status.PUBLISHED
    assert project.start_year == 2026
    assert project.end_year is None
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


@pytest.mark.django_db
@pytest.mark.parametrize("start_year", ["999", "10000", "2025-01-01", "2025.5"])
def test_admin_rejects_invalid_years(admin_client, start_year):
    data = project_data(published=False)
    data["start_year"] = start_year
    response = admin_client.post(reverse("admin:projects_project_add"), data)
    assert response.status_code == 200
    assert "start_year" in response.context["adminform"].form.errors
    assert not Project.objects.exists()
