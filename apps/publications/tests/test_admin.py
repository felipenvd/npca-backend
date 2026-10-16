import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.html import strip_tags

from apps.accounts.models import User
from apps.publications.models import Publication, PublicationAuthor
from apps.researchers.models import Researcher


def publication_data(*, published: bool, complete_english: bool = False) -> dict[str, str]:
    return {
        "status": Publication.Status.PUBLISHED if published else Publication.Status.DRAFT,
        "cover_credit": "",
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
    assert 'name="translations-0-language" value="pt-br"' in content
    assert 'name="translations-1-language" value="en"' in content
    assert "Título *" in strip_tags(content)
    assert "Resumo *" in strip_tags(content)
    assert "Ano *" in strip_tags(content)
    assert "Periódico ou evento *" in strip_tags(content)
    assert "Pesquisador cadastrado" in content
    assert "Nome do autor externo" in content
    assert "Imagem de divulgação" in content
    assert "Texto alternativo da imagem" not in content
    assert 'name="translations-0-cover_alt_text"' not in content
    assert 'name="translations-1-cover_alt_text"' not in content
    assert "Arquivo PDF" not in content
    assert 'name="document"' not in content
    assert "Arquivo atual" not in content
    assert 'name="external_url"' in content
    assert 'name="doi"' in content
    assert "publications/admin/author_order.js" in content
    authors = response.context["inline_admin_formsets"][1].formset
    assert authors.extra_forms[0]["display_order"].value() == 1


@pytest.mark.django_db
def test_suggested_author_order_does_not_create_an_empty_author(admin_client):
    data = publication_data(published=False)
    data["author_records-0-display_order"] = "1"

    response = admin_client.post(reverse("admin:publications_publication_add"), data)

    assert response.status_code == 302
    assert Publication.objects.count() == 1
    assert not PublicationAuthor.objects.exists()


@pytest.mark.django_db
def test_author_order_continues_existing_sequence_and_preserves_manual_values(admin_client):
    from apps.core.tests.test_bilingual_admin import FormValues

    publication = Publication.objects.create()
    PublicationAuthor.objects.create(publication=publication, external_name="Ana", display_order=0)
    PublicationAuthor.objects.create(publication=publication, external_name="Bia", display_order=1)
    url = reverse("admin:publications_publication_change", args=[publication.pk])
    response = admin_client.get(url)
    values = FormValues(response.content.decode(), "publication_form").values
    assert values["author_records-0-display_order"] == "0"
    assert values["author_records-1-display_order"] == "1"
    assert values["author_records-2-display_order"] == "2"
    values["author_records-2-external_name"] = "Clara"
    values["author_records-2-display_order"] = "8"
    values["_save"] = "Salvar"

    saved = admin_client.post(url, values)

    assert saved.status_code == 302
    assert list(publication.author_records.values_list("display_order", flat=True)) == [0, 1, 8]
    next_page = admin_client.get(url)
    next_values = FormValues(next_page.content.decode(), "publication_form").values
    assert next_values["author_records-3-display_order"] == "9"


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


@pytest.mark.django_db
def test_editing_publication_preserves_previously_registered_alt_text(admin_client):
    from apps.core.tests.test_bilingual_admin import FormValues

    response = admin_client.post(
        reverse("admin:publications_publication_add"),
        publication_data(published=False, complete_english=True),
    )
    assert response.status_code == 302
    publication = Publication.objects.get()
    publication.translations.filter(language="pt-br").update(
        cover_alt_text="Descrição já cadastrada"
    )
    publication.translations.filter(language="en").update(
        cover_alt_text="Previously registered description"
    )
    url = reverse("admin:publications_publication_change", args=[publication.pk])
    page = admin_client.get(url)
    values = FormValues(page.content.decode(), "publication_form").values
    assert not any("cover_alt_text" in name for name in values)
    values["_save"] = "Salvar"

    updated = admin_client.post(url, values)

    assert updated.status_code == 302
    assert (
        publication.translations.get(language="pt-br").cover_alt_text == "Descrição já cadastrada"
    )
    assert (
        publication.translations.get(language="en").cover_alt_text
        == "Previously registered description"
    )


@pytest.mark.django_db
def test_admin_does_not_store_files_submitted_to_the_removed_pdf_field(
    admin_client, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    data = publication_data(published=False)
    data["document"] = SimpleUploadedFile(
        "paper.pdf", b"%PDF-1.7\ncontent", content_type="application/pdf"
    )

    response = admin_client.post(reverse("admin:publications_publication_add"), data)

    assert response.status_code == 302
    assert Publication.objects.count() == 1
    assert "document" not in {field.name for field in Publication._meta.get_fields()}
    assert not list(tmp_path.rglob("*.pdf"))
