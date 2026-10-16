import pytest
from django.urls import reverse
from django.utils.html import strip_tags

from apps.accounts.models import User
from apps.researchers.models import Researcher


def researcher_data(*, active: bool) -> dict[str, str | bool]:
    return {
        "full_name": "Ana Silva",
        "academic_category": Researcher.AcademicCategory.DOCTOR,
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
        "translations-0-research_area": "Inteligência Artificial",
        "translations-0-biography_html": "<p>Biografia</p>",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-slug": "",
        "translations-1-research_area": "",
        "translations-1-biography_html": "",
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
    assert 'name="translations-0-language" value="pt-br"' in content
    assert 'name="translations-1-language" value="en"' in content
    assert "Os campos marcados com * são obrigatórios para ativar" in content
    assert "Área de pesquisa *" in strip_tags(content)
    assert "Biografia *" in strip_tags(content)
    assert "Função *" not in content
    assert "Texto alternativo da foto" not in content
    assert "Gerado automaticamente a partir do nome" in content
    assert "Categoria acadêmica" in content
    assert content.index("Nome completo") < content.index("Categoria acadêmica")
    assert content.index("Ativo") < content.index("Categoria acadêmica")
    assert "dentro da categoria acadêmica" in content


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
            "translations-1-research_area": "Artificial Intelligence",
            "translations-1-biography_html": "<p>Biography</p>",
        }
    )
    valid_response = client.post(reverse("admin:researchers_researcher_add"), data)

    assert valid_response.status_code == 302
    researcher = Researcher.objects.get()
    assert researcher.is_active is True
    assert set(researcher.translations.values_list("language", flat=True)) == {"pt-br", "en"}


@pytest.mark.django_db
def test_changelist_saves_display_order_without_changing_photos(admin_client):
    researcher = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        display_order=1,
        photo="researchers/photos/original.jpg",
        photo_cropped="researchers/cropped/avatar.webp",
        photo_crop={"x": 50, "y": 10, "zoom": 1.5},
    )
    other = Researcher.objects.create(
        full_name="Bruno Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        display_order=2,
    )
    url = reverse("admin:researchers_researcher_changelist")
    response = admin_client.get(url)
    formset = response.context["cl"].formset
    assert len(formset.forms) == 2
    values = {
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "2",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "_save": "Salvar",
    }
    for form in formset.forms:
        values[f"{form.prefix}-id"] = str(form.instance.pk)
        values[f"{form.prefix}-display_order"] = "3" if form.instance.pk == researcher.pk else "0"

    response = admin_client.post(url, values)

    assert response.status_code == 302
    researcher.refresh_from_db()
    other.refresh_from_db()
    assert researcher.display_order == 3
    assert other.display_order == 0
    assert researcher.photo.name == "researchers/photos/original.jpg"
    assert researcher.photo_cropped.name == "researchers/cropped/avatar.webp"
    assert researcher.photo_crop == {"x": 50, "y": 10, "zoom": 1.5}
    assert researcher.updated_by_id == int(admin_client.session["_auth_user_id"])
    assert not other.photo
    assert not other.photo_cropped


@pytest.mark.django_db
def test_admin_activates_undergraduate_without_research_area_or_biography(admin_client):
    data = researcher_data(active=True)
    data["academic_category"] = Researcher.AcademicCategory.UNDERGRADUATE_RESEARCHER
    for index in range(2):
        data[f"translations-{index}-research_area"] = ""
        data[f"translations-{index}-biography_html"] = ""

    response = admin_client.post(reverse("admin:researchers_researcher_add"), data)

    assert response.status_code == 302
    researcher = Researcher.objects.get()
    assert researcher.is_active
    researcher.validate_for_activation()
    assert researcher.translations.count() == 2
    for language in ("pt-br", "en"):
        translation = researcher.translations.get(language=language)
        assert translation.slug == "ana-silva"
        detail = admin_client.get(f"/api/v1/researchers/{translation.slug}", {"lang": language})
        assert detail.status_code == 200
        assert detail.json()["research_area"] == ""
        assert detail.json()["biography_html"] == ""

    # A category change must restore the activation requirements on the server.
    from apps.core.tests.test_bilingual_admin import FormValues

    url = reverse("admin:researchers_researcher_change", args=[researcher.pk])
    page = admin_client.get(url)
    values = FormValues(page.content.decode(), "researcher_form").values
    values.update({"academic_category": "doctor", "_save": "Salvar"})
    invalid = admin_client.post(url, values)
    assert invalid.status_code == 200
    researcher.refresh_from_db()
    assert researcher.academic_category == Researcher.AcademicCategory.UNDERGRADUATE_RESEARCHER
    assert "Preencha área de pesquisa" in invalid.content.decode()
    assert "Preencha biografia" in invalid.content.decode()

    for index in range(2):
        values[f"translations-{index}-research_area"] = "Área de pesquisa"
        values[f"translations-{index}-biography_html"] = "<p>Biografia</p>"
    valid = admin_client.post(url, values)
    assert valid.status_code == 302
    researcher.refresh_from_db()
    assert researcher.academic_category == Researcher.AcademicCategory.DOCTOR
    researcher.validate_for_activation()


def test_admin_marks_research_content_as_required_according_to_category(admin_client):
    response = admin_client.get(reverse("admin:researchers_researcher_add"))
    html = response.content.decode()
    assert html.count('data-required-controller="academic_category"') == 4
    assert 'data-required-values="doctor,doctoral_student,master,masters_student"' in html
    assert "Opcional para graduandos de iniciação científica" in html
