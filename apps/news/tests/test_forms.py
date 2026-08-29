import pytest
from django.forms import inlineformset_factory

from apps.news.forms import NewsTranslationForm, NewsTranslationInlineFormSet
from apps.news.models import News, NewsTranslation


def translation_formset(data: dict, instance: News):
    formset_class = inlineformset_factory(
        News,
        NewsTranslation,
        form=NewsTranslationForm,
        formset=NewsTranslationInlineFormSet,
        extra=2,
        max_num=2,
        can_delete=False,
    )
    return formset_class(data=data, instance=instance, prefix="translations")


def management_data(total: int = 2) -> dict[str, str]:
    return {
        "translations-TOTAL_FORMS": str(total),
        "translations-INITIAL_FORMS": "0",
        "translations-MIN_NUM_FORMS": "0",
        "translations-MAX_NUM_FORMS": "2",
    }


@pytest.mark.django_db
def test_draft_accepts_incomplete_translation() -> None:
    news = News(status=News.Status.DRAFT)
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-title": "Título",
        "translations-1-language": "en",
    }

    formset = translation_formset(data, news)

    assert formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_publishing_requires_two_complete_translations() -> None:
    news = News(status=News.Status.PUBLISHED)
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-title": "Título",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Conteúdo</p>",
        "translations-1-language": "en",
        "translations-1-title": "",
    }

    formset = translation_formset(data, news)

    assert not formset.is_valid()
    assert "Preencha título na tradução em English" in str(formset.non_form_errors())


@pytest.mark.django_db
def test_complete_bilingual_news_can_be_published() -> None:
    news = News(status=News.Status.PUBLISHED)
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-title": "Título",
        "translations-0-slug": "",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Conteúdo</p>",
        "translations-1-language": "en",
        "translations-1-title": "Title",
        "translations-1-slug": "",
        "translations-1-summary": "Summary",
        "translations-1-body_html": "<p>Content</p>",
    }

    formset = translation_formset(data, news)

    assert formset.is_valid(), (formset.errors, formset.non_form_errors())
    assert formset.forms[0].cleaned_data["slug"] == "titulo"
    assert formset.forms[1].cleaned_data["slug"] == "title"


@pytest.mark.django_db
def test_published_news_with_cover_requires_alt_text_in_both_languages() -> None:
    news = News(status=News.Status.PUBLISHED)
    news.cover.name = "news/covers/example.webp"
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-title": "Título",
        "translations-0-summary": "Resumo",
        "translations-0-body_html": "<p>Conteúdo</p>",
        "translations-0-cover_alt_text": "Descrição",
        "translations-1-language": "en",
        "translations-1-title": "Title",
        "translations-1-summary": "Summary",
        "translations-1-body_html": "<p>Content</p>",
    }

    formset = translation_formset(data, news)

    assert not formset.is_valid()
    assert "texto alternativo da capa em English" in str(formset.non_form_errors())


def test_translation_form_explains_publication_requirements() -> None:
    form = NewsTranslationForm()

    for field_name in ("title", "summary", "body_html"):
        field = form.fields[field_name]
        assert field.label.endswith(" *")
        assert field.help_text == "Obrigatório para publicar."
        assert field.required is False

    assert "Gerado automaticamente" in form.fields["slug"].help_text
    assert "quando houver imagem de capa" in form.fields["cover_alt_text"].help_text
    assert form.fields["seo_title"].help_text.startswith("Opcional.")
    assert form.fields["seo_description"].help_text.startswith("Opcional.")
