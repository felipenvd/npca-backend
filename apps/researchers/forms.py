from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.widgets import UnfoldAdminURLInputWidget

from apps.core.sanitizers import sanitize_rich_text

from .models import Researcher, ResearcherTranslation, activation_errors
from .photos import cropped_photo, validate_photo_crop
from .widgets import ResearcherPhotoWidget


class ResearcherForm(forms.ModelForm):
    lattes_url = forms.URLField(
        label="Currículo Lattes",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )
    orcid_url = forms.URLField(
        label="ORCID",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )
    linkedin_url = forms.URLField(
        label="LinkedIn",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )

    class Meta:
        model = Researcher
        fields = (
            "full_name",
            "academic_category",
            "photo",
            "photo_crop",
            "public_email",
            "lattes_url",
            "orcid_url",
            "linkedin_url",
            "is_active",
            "display_order",
        )
        widgets = {"photo": ResearcherPhotoWidget(), "photo_crop": forms.HiddenInput()}
        help_texts = {
            "display_order": "Define a posição do pesquisador dentro da categoria acadêmica."
        }

    def clean_photo_crop(self):
        if self.add_prefix("photo_crop") not in self.data:
            crop = (
                {}
                if self.files.get(self.add_prefix("photo"))
                else self.initial.get("photo_crop", {})
            )
        else:
            crop = self.cleaned_data.get("photo_crop")
            if crop is None:
                crop = {}
        validate_photo_crop(crop)
        return crop

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.photo_crop = self.cleaned_data["photo_crop"]
        if commit:
            self.prepare_photo_crop()
            instance.save()
            self.save_m2m()
        return instance

    def prepare_photo_crop(self):
        instance = self.instance
        if not instance.photo:
            instance.photo_crop = {}
            instance.photo_cropped = ""
        elif self.files.get(
            self.add_prefix("photo")
        ) is not None or instance.photo_crop != self.initial.get("photo_crop", {}):
            result = cropped_photo(instance.photo, instance.photo_crop)
            instance.photo_cropped.save(result.name, result, save=False)


class ResearcherTranslationForm(forms.ModelForm):
    class Meta:
        model = ResearcherTranslation
        fields = (
            "language",
            "slug",
            "research_area",
            "biography_html",
            "seo_title",
            "seo_description",
        )
        widgets = {"biography_html": WysiwygWidget()}
        labels = {
            "research_area": "Área de pesquisa *",
            "biography_html": "Biografia *",
        }
        help_texts = {
            "slug": (
                "Gerado automaticamente a partir do nome quando deixado em branco. "
                "Depois de ativado, altere somente se também for atualizar a URL."
            ),
            "research_area": (
                "Opcional para graduandos de iniciação científica. "
                "Obrigatório para ativar nas demais categorias."
            ),
            "biography_html": (
                "Opcional para graduandos de iniciação científica. "
                "Obrigatório para ativar nas demais categorias."
            ),
            "seo_title": "Opcional. Quando vazio, o nome será usado.",
            "seo_description": "Opcional. Quando vazia, a área de pesquisa será usada.",
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
            errors = activation_errors(translations, self.instance.academic_category)
            if errors:
                raise ValidationError(errors)
