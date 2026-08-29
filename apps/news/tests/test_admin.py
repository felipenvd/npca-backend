import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.news.models import News


@pytest.mark.django_db
def test_admin_add_page_uses_wysiwyg_and_two_locales(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    response = client.get(reverse("admin:news_news_add"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "unfold/forms/js/trix/trix.js" in content
    assert 'value="pt-br" selected' in content
    assert 'value="en" selected' in content
    assert "Os campos marcados com * são obrigatórios para publicar" in content
    assert "Título *" in content
    assert "Resumo *" in content
    assert "Conteúdo *" in content
    assert "Gerado automaticamente a partir do título" in content
    assert "Texto alternativo da capa" not in content


@pytest.mark.django_db
def test_admin_records_creation_and_update_users(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = {
        "status": News.Status.DRAFT,
        "cover_credit": "",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Notícia em preparação",
        "translations-0-slug": "",
        "translations-0-summary": "",
        "translations-0-body_html": "",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-title": "",
        "translations-1-slug": "",
        "translations-1-summary": "",
        "translations-1-body_html": "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "_save": "Salvar",
    }

    response = client.post(reverse("admin:news_news_add"), data)

    assert response.status_code == 302
    news = News.objects.get()
    assert news.created_by == admin_user
    assert news.updated_by == admin_user
    assert news.translations.get(language="pt-br").slug == "noticia-em-preparacao"


@pytest.mark.django_db
def test_admin_blocks_incomplete_publication_and_accepts_complete_bilingual_news(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)
    data = {
        "status": News.Status.PUBLISHED,
        "cover_credit": "",
        "translations-TOTAL_FORMS": "2",
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
        "translations-0-language": "pt-br",
        "translations-0-title": "Notícia publicada",
        "translations-0-slug": "noticia-publicada",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Conteúdo</p>",
        "translations-0-seo_title": "",
        "translations-0-seo_description": "",
        "translations-1-language": "en",
        "translations-1-title": "",
        "translations-1-slug": "",
        "translations-1-summary": "",
        "translations-1-body_html": "",
        "translations-1-seo_title": "",
        "translations-1-seo_description": "",
        "_save": "Salvar",
    }

    invalid_response = client.post(reverse("admin:news_news_add"), data)

    assert invalid_response.status_code == 200
    assert not News.objects.exists()

    data.update(
        {
            "translations-1-title": "Published news",
            "translations-1-slug": "published-news",
            "translations-1-summary": "Summary",
            "translations-1-body_html": "<p>Content</p>",
        }
    )
    valid_response = client.post(reverse("admin:news_news_add"), data)

    assert valid_response.status_code == 302
    news = News.objects.get()
    assert news.status == News.Status.PUBLISHED
    assert news.published_at is not None
    assert set(news.translations.values_list("language", flat=True)) == {"pt-br", "en"}
