from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from unfold.widgets import UnfoldAdminURLInputWidget

from .models import (
    Publication,
    PublicationAuthor,
    PublicationTranslation,
    normalize_doi,
    publication_errors,
)


class PublicationForm(forms.ModelForm):
    external_url = forms.URLField(
        label="URL externa",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )

    class Meta:
        model = Publication
        fields = (
            "status",
            "year",
            "venue",
            "doi",
            "external_url",
            "document",
            "project",
            "display_order",
        )
        labels = {
            "year": "Ano *",
            "venue": "Periódico ou evento *",
        }
        help_texts = {
            "year": "Obrigatório para publicar.",
            "venue": "Obrigatório para publicar.",
            "doi": "Opcional. Aceita o identificador ou uma URL doi.org.",
            "document": (
                "Opcional. Envie somente quando a distribuição do PDF for permitida; "
                "limite de 20 MiB."
            ),
            "display_order": "Desempata publicações do mesmo ano.",
        }

    def clean_doi(self) -> str:
        return normalize_doi(self.cleaned_data.get("doi") or "")


class PublicationTranslationForm(forms.ModelForm):
    class Meta:
        model = PublicationTranslation
        fields = ("language", "title", "abstract", "seo_title", "seo_description")
        labels = {"title": "Título *", "abstract": "Resumo *"}
        help_texts = {
            "title": "Obrigatório para publicar.",
            "abstract": "Obrigatório para publicar.",
            "seo_title": "Opcional. Quando vazio, o título da publicação será usado.",
            "seo_description": "Opcional. Quando vazia, o resumo será usado.",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["language"].disabled = True


class PublicationTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in PublicationTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, PublicationTranslation] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            language = form.cleaned_data.get("language")
            if not language:
                continue
            if language in translations:
                raise ValidationError("Cada idioma deve aparecer apenas uma vez.")
            translations[language] = form.save(commit=False)

        if self.instance.status == Publication.Status.PUBLISHED:
            errors = publication_errors(translations)
            if errors:
                raise ValidationError(errors)


class PublicationAuthorForm(forms.ModelForm):
    class Meta:
        model = PublicationAuthor
        fields = ("researcher", "external_name", "display_order")
        help_texts = {
            "researcher": "Use este campo quando o autor estiver cadastrado no NPCA.",
            "external_name": "Use somente para autores que não estão cadastrados.",
            "display_order": "Use 1 para o primeiro autor, 2 para o segundo e assim por diante.",
        }


class PublicationAuthorInlineFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        seen_researchers: set[int] = set()
        seen_orders: set[int] = set()
        authors = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            researcher = form.cleaned_data.get("researcher")
            external_name = (form.cleaned_data.get("external_name") or "").strip()
            display_order = form.cleaned_data.get("display_order")
            if researcher is None and not external_name:
                continue
            authors += 1
            if researcher is not None and external_name:
                raise ValidationError(
                    "Cada autor deve usar um pesquisador cadastrado ou um nome externo."
                )
            if researcher is not None:
                if researcher.pk in seen_researchers:
                    raise ValidationError("Cada pesquisador deve aparecer apenas uma vez.")
                seen_researchers.add(researcher.pk)
            if display_order in seen_orders:
                raise ValidationError("Cada autor deve ter uma ordem diferente.")
            if display_order is not None:
                seen_orders.add(display_order)

        if self.instance.status == Publication.Status.PUBLISHED and authors == 0:
            raise ValidationError("Informe pelo menos um autor antes de publicar.")
