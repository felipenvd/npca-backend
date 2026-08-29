from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.news.models import News, NewsTranslation


@pytest.mark.django_db
def test_incomplete_draft_can_be_saved() -> None:
    news = News.objects.create()
    translation = NewsTranslation.objects.create(news=news, language="pt-br")

    assert news.status == News.Status.DRAFT
    assert translation.slug is None


@pytest.mark.django_db
def test_translation_generates_slug_and_sanitizes_html() -> None:
    news = News.objects.create()
    translation = NewsTranslation.objects.create(
        news=news,
        language="pt-br",
        title="Ciência na Amazônia",
        body_html=(
            '<h2 onclick="alert(1)">Título</h2><script>alert(1)</script>'
            '<a href="javascript:alert(1)">link</a><strong>seguro</strong>'
        ),
    )

    assert translation.slug == "ciencia-na-amazonia"
    assert "script" not in translation.body_html
    assert "onclick" not in translation.body_html
    assert "javascript:" not in translation.body_html
    assert "<h2>Título</h2>" in translation.body_html
    assert "<strong>seguro</strong>" in translation.body_html


@pytest.mark.django_db
def test_language_and_slug_constraints_are_enforced() -> None:
    first = News.objects.create()
    second = News.objects.create()
    NewsTranslation.objects.create(
        news=first,
        language="pt-br",
        title="Primeira",
        slug="mesmo-slug",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        NewsTranslation.objects.create(
            news=first,
            language="pt-br",
            title="Duplicada",
            slug="outro-slug",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        NewsTranslation.objects.create(
            news=second,
            language="pt-br",
            title="Outro conteúdo",
            slug="mesmo-slug",
        )


@pytest.mark.django_db
def test_first_publication_date_is_preserved() -> None:
    news = News.objects.create()
    news.status = News.Status.PUBLISHED
    news.save()
    first_publication = news.published_at

    news.status = News.Status.DRAFT
    news.save()
    news.status = News.Status.PUBLISHED
    news.save()

    assert first_publication is not None
    assert timezone.now() - first_publication < timedelta(seconds=2)
    assert news.published_at == first_publication
