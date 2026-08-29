from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from unfold.contrib.forms.widgets import WysiwygWidget

from apps.core.sanitizers import sanitize_rich_text

from .models import Researcher, ResearcherTranslation, activation_errors


class ResearcherForm(forms.ModelForm):
    lattes_url = forms.URLField(
        label="Currículo Lattes",
        required=False,
        assume_scheme="https",
    )
    orcid_url = forms.URLField(label="ORCID", required=False, assume_scheme="https")
    linkedin_url = forms.URLField(label="LinkedIn", required=False, assume_scheme="https")

    class Meta:
        model = Researcher
        fields = (
            "full_name",
            "academic_category",
            "photo",
            "public_email",
            "lattes_url",
            "orcid_url",
            "linkedin_url",
            "is_active",
            "display_order",
        )
        help_texts = {
            "display_order": "Define a posição do pesquisador dentro da categoria acadêmica."
        }


class ResearcherTranslationForm(forms.ModelForm):
    class Meta:
        model = ResearcherTranslation
        fields = (
            "language",
            "slug",
            "role",
            "research_area",
            "biography_html",
            "photo_alt_text",
            "seo_title",
            "seo_description",
        )
        widgets = {"biography_html": WysiwygWidget()}
        labels = {
            "role": "Função *",
            "research_area": "Área de pesquisa *",
            "biography_html": "Biografia *",
        }
        help_texts = {
            "slug": (
                "Gerado automaticamente a partir do nome quando deixado em branco. "
                "Depois de ativado, altere somente se também for atualizar a URL."
            ),
            "role": "Obrigatório para ativar.",
            "research_area": "Obrigatório para ativar.",
            "biography_html": "Obrigatório para ativar.",
            "photo_alt_text": "Obrigatório para ativar quando houver foto.",
            "seo_title": "Opcional. Quando vazio, o nome será usado.",
            "seo_description": "Opcional. Quando vazia, função e área serão usadas.",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["language"].disabled = True

    def clean(self) -> dict:
        cleaned_data = super().clean()
        slug = (cleaned_data.get("slug") or "").strip()
        cleaned_data["slug"] = slug or self.instance.default_slug()
        cleaned_data["biography_html"] = sanitize_rich_text(
            cleaned_data.get("biography_html") or ""
        )
        return cleaned_data


class ResearcherTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in ResearcherTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, ResearcherTranslation] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            language = form.cleaned_data.get("language")
            if not language:
                continue
            if language in translations:
                raise ValidationError("Cada idioma deve aparecer apenas uma vez.")

            translation = form.save(commit=False)
            translation.slug = translation.slug or (
                slugify(self.instance.full_name) if self.instance.full_name else None
            )
            form.cleaned_data["slug"] = translation.slug
            translations[language] = translation

        if self.instance.is_active:
            errors = activation_errors(self.instance, translations)
            if errors:
                raise ValidationError(errors)
