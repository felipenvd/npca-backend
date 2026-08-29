import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.publications.models import Publication
from apps.researchers.models import Researcher


def publication_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    return {
        "status": Publication.Status.PUBLISHED if published else Publication.Status.DRAFT,
        "year": "",
        "venue": "",
        "doi": "https://doi.org/10.1000/EXAMPLE",
        "external_url": "",
        "project": "",
        "display_order": "0",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Computação na Amazônia",
        "translations-0-abstract": "Resumo",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-title": "Computing in the Amazon" if complete_english else "",
        "translations-1-abstract": "Abstract" if complete_english else "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "author_records-TOTAL_FORMS": "1",
        "author_records-INITIAL_FORMS": "0",
        "author_records-MIN_NUM_FORMS": "0",
        "author_records-MAX_NUM_FORMS": "1000",
        "author_records-0-researcher": "",
        "author_records-0-external_name": "",
        "author_records-0-display_order": "0",
        "_save": "Salvar",
    }


@pytest.mark.django_db
def test_admin_add_page_exposes_bilingual_editorial_and_author_fields(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:publications_publication_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'value="pt-br" selected' in content
    assert 'value="en" selected' in content
    assert "Título *" in content
    assert "Resumo *" in content
    assert "Ano *" in content
    assert "Periódico ou evento *" in content
    assert "Pesquisador cadastrado" in content
    assert "Nome do autor externo" in content
    assert "Arquivo PDF" in content


@pytest.mark.django_db
def test_admin_allows_incomplete_draft_normalizes_doi_and_records_audit(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:publications_publication_add"),
        publication_data(published=False),
    )

    assert response.status_code == 302
    publication = Publication.objects.get()
    assert publication.doi == "10.1000/example"
    assert publication.created_by == admin_user
    assert publication.updated_by == admin_user


@pytest.mark.django_db
def test_admin_blocks_incomplete_publication_and_accepts_complete_record(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    author = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    client.force_login(admin_user)
    data = publication_data(published=True)

    invalid_response = client.post(reverse("admin:publications_publication_add"), data)

    assert invalid_response.status_code == 200
    assert not Publication.objects.exists()

    data.update(
        {
            "year": "2026",
            "venue": "Simpósio de Computação Aplicada",
            "translations-1-title": "Computing in the Amazon",
            "translations-1-abstract": "Abstract",
            "author_records-0-researcher": str(author.pk),
            "author_records-0-display_order": "1",
        }
    )
    valid_response = client.post(reverse("admin:publications_publication_add"), data)

    assert valid_response.status_code == 302
    publication = Publication.objects.get()
    assert publication.status == Publication.Status.PUBLISHED
    assert publication.author_records.get().researcher == author
    assert publication.published_at is not None
