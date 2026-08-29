from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from unfold.contrib.forms.widgets import WysiwygWidget

from .models import News, NewsTranslation, publication_errors
from .sanitizers import sanitize_rich_text


class NewsTranslationForm(forms.ModelForm):
    class Meta:
        model = NewsTranslation
        fields = (
            "language",
            "title",
            "slug",
            "summary",
            "body_html",
            "cover_alt_text",
            "seo_title",
            "seo_description",
        )
        widgets = {"body_html": WysiwygWidget()}
        labels = {
            "title": "Título *",
            "summary": "Resumo *",
            "body_html": "Conteúdo *",
        }
        help_texts = {
            "title": "Obrigatório para publicar.",
            "slug": (
                "Gerado automaticamente a partir do título quando deixado em branco. "
                "Depois de publicado, altere somente se também for atualizar a URL."
            ),
            "summary": "Obrigatório para publicar.",
            "body_html": "Obrigatório para publicar.",
            "cover_alt_text": "Obrigatório para publicar quando houver imagem de capa.",
            "seo_title": "Opcional. Quando vazio, o título da notícia será usado.",
            "seo_description": "Opcional. Quando vazia, o resumo será usado.",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["language"].disabled = True

    def clean(self) -> dict:
        cleaned_data = super().clean()
        title = (cleaned_data.get("title") or "").strip()
        slug = (cleaned_data.get("slug") or "").strip()
        body_html = cleaned_data.get("body_html") or ""
        cleaned_data["slug"] = slug or (slugify(title) if title else None)
        cleaned_data["body_html"] = sanitize_rich_text(body_html)
        return cleaned_data


class NewsTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in NewsTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, NewsTranslation] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            language = form.cleaned_data.get("language")
            if not language:
                continue
            if language in translations:
                raise ValidationError("Cada idioma deve aparecer apenas uma vez.")

            translation = form.save(commit=False)
            translations[language] = translation

        if self.instance.status == News.Status.PUBLISHED:
            errors = publication_errors(self.instance, translations)
            if errors:
                raise ValidationError(errors)
