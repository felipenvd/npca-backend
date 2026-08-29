import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.researchers.models import Researcher


def researcher_data(*, active: bool) -> dict[str, str | bool]:
    return {
        "full_name": "Ana Silva",
        "is_active": active,
        "display_order": "1",
        "public_email": "ana@ufra.edu.br",
        "lattes_url": "",
        "orcid_url": "",
        "linkedin_url": "",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-slug": "",
        "translations-0-role": "Professora",
        "translations-0-research_area": "Inteligência Artificial",
        "translations-0-biography_html": "<p>Biografia</p>",
        "translations-0-photo_alt_text": "",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-slug": "",
        "translations-1-role": "",
        "translations-1-research_area": "",
        "translations-1-biography_html": "",
        "translations-1-photo_alt_text": "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "_save": "Salvar",
    }


@pytest.mark.django_db
def test_admin_add_page_uses_wysiwyg_and_two_locales(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:researchers_researcher_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "unfold/forms/js/trix/trix.js" in content
    assert 'value="pt-br" selected' in content
    assert 'value="en" selected' in content
    assert "Os campos marcados com * são obrigatórios para ativar" in content
    assert "Função *" in content
    assert "Área de pesquisa *" in content
    assert "Biografia *" in content
    assert "Gerado automaticamente a partir do nome" in content


@pytest.mark.django_db
def test_admin_records_audit_and_allows_incomplete_inactive_researcher(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:researchers_researcher_add"),
        researcher_data(active=False),
    )

    assert response.status_code == 302
    researcher = Researcher.objects.get()
    assert researcher.created_by == admin_user
    assert researcher.updated_by == admin_user
    assert researcher.translations.get(language="pt-br").slug == "ana-silva"


@pytest.mark.django_db
def test_admin_blocks_incomplete_activation_and_accepts_complete_bilingual_profile(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = researcher_data(active=True)

    invalid_response = client.post(reverse("admin:researchers_researcher_add"), data)

    assert invalid_response.status_code == 200
    assert not Researcher.objects.exists()

    data.update(
        {
            "translations-1-role": "Professor",
            "translations-1-research_area": "Artificial Intelligence",
            "translations-1-biography_html": "<p>Biography</p>",
        }
    )
    valid_response = client.post(reverse("admin:researchers_researcher_add"), data)

    assert valid_response.status_code == 302
    researcher = Researcher.objects.get()
    assert researcher.is_active is True
    assert set(researcher.translations.values_list("language", flat=True)) == {"pt-br", "en"}
