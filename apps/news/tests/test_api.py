from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.news.models import News, NewsTranslation


def create_published_news(
    *,
    pt_slug: str,
    en_slug: str,
    title: str,
    cover=None,
) -> News:
    news = News.objects.create(cover=cover)
    NewsTranslation.objects.create(
        news=news,
        language="pt-br",
        title=title,
        slug=pt_slug,
        summary=f"Resumo de {title}",
        body_html=f"<p>Conteúdo de {title}</p>",
        cover_alt_text="Capa da notícia" if cover else "",
    )
    NewsTranslation.objects.create(
        news=news,
        language="en",
        title=f"{title} in English",
        slug=en_slug,
        summary=f"Summary of {title}",
        body_html=f"<p>Content of {title}</p>",
        cover_alt_text="News cover" if cover else "",
    )
    news.status = News.Status.PUBLISHED
    news.save()
    return news


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (32, 24), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("cover.webp", buffer.getvalue(), content_type="image/webp")


@pytest.mark.django_db
def test_list_requires_valid_language(client) -> None:
    missing = client.get("/api/v1/news")
    invalid = client.get("/api/v1/news", {"lang": "fr"})

    assert missing.status_code == 422
    assert invalid.status_code == 422
    assert missing["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_list_returns_only_published_news_in_requested_language(client) -> None:
    create_published_news(pt_slug="publicada", en_slug="published", title="Publicada")
    draft = News.objects.create()
    NewsTranslation.objects.create(
        news=draft,
        language="pt-br",
        title="Rascunho",
        slug="rascunho",
    )
    archived = create_published_news(pt_slug="arquivada", en_slug="archived", title="Arquivada")
    archived.status = News.Status.ARCHIVED
    archived.save()

    response = client.get("/api/v1/news", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["slug"] for item in response.json()["items"]] == ["publicada"]


@pytest.mark.django_db
def test_list_is_paginated_and_ordered_by_publication(client) -> None:
    create_published_news(pt_slug="primeira", en_slug="first", title="Primeira")
    create_published_news(pt_slug="segunda", en_slug="second", title="Segunda")

    response = client.get(
        "/api/v1/news",
        {"lang": "pt-br", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["page_size"] == 1
    assert response.json()["items"][0]["slug"] == "segunda"


@pytest.mark.django_db
def test_detail_returns_sanitized_body_seo_fallback_and_translation_slugs(client) -> None:
    create_published_news(pt_slug="noticia", en_slug="news", title="Notícia")

    response = client.get("/api/v1/news/noticia", {"lang": "pt-br"})

    assert response.status_code == 200
    body = response.json()
    assert body["body_html"] == "<p>Conteúdo de Notícia</p>"
    assert body["seo_title"] == "Notícia"
    assert body["seo_description"] == "Resumo de Notícia"
    assert body["translations"] == [
        {"lang": "en", "slug": "news"},
        {"lang": "pt-br", "slug": "noticia"},
    ]


@pytest.mark.django_db
def test_detail_hides_unpublished_and_wrong_language_slugs(client) -> None:
    news = create_published_news(pt_slug="noticia", en_slug="news", title="Notícia")

    wrong_language = client.get("/api/v1/news/noticia", {"lang": "en"})
    news.status = News.Status.DRAFT
    news.save()
    draft = client.get("/api/v1/news/noticia", {"lang": "pt-br"})

    assert wrong_language.status_code == 404
    assert draft.status_code == 404
    assert draft["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_cover_uses_relative_media_url(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path
    news = create_published_news(
        pt_slug="com-capa",
        en_slug="with-cover",
        title="Com capa",
        cover=webp_upload(),
    )
    news.cover_credit = "Arquivo NPCA"
    news.save()

    response = client.get("/api/v1/news/com-capa", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json()["cover"] == {
        "url": f"/media/{news.cover.name}",
        "alt": "Capa da notícia",
        "credit": "Arquivo NPCA",
    }
