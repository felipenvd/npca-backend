from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from unfold.widgets import UnfoldAdminURLInputWidget

from .models import Course, CourseTranslation, course_publication_errors


class CourseForm(forms.ModelForm):
    external_url = forms.URLField(
        label="URL externa *",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )

    class Meta:
        model = Course
        fields = (
            "status",
            "course_type",
            "external_url",
            "cover",
            "cover_credit",
            "is_featured",
            "display_order",
        )
        labels = {
            "course_type": "Tipo *",
            "external_url": "URL externa *",
        }
        help_texts = {
            "course_type": "Obrigatório para publicar.",
            "external_url": (
                "Obrigatória para publicar. Informe somente uma URL externa iniciada por https://."
            ),
            "cover": "Opcional. Use uma imagem JPEG, PNG ou WebP de até 5 MiB.",
            "cover_credit": "Opcional. Informe a autoria ou a fonte da imagem.",
            "is_featured": "Itens destacados podem aparecer na página inicial.",
            "display_order": "Menores valores aparecem primeiro.",
        }


class CourseTranslationForm(forms.ModelForm):
    class Meta:
        model = CourseTranslation
        fields = ("language", "title", "summary", "cover_alt_text")
        labels = {"title": "Título *", "summary": "Resumo *"}
        help_texts = {
            "title": "Obrigatório para publicar.",
            "summary": "Obrigatório para publicar.",
            "cover_alt_text": (
                "Descreva a imagem quando ela transmitir informação relevante. "
                "Deixe vazio quando for apenas decorativa."
            ),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["language"].disabled = True


class CourseTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in CourseTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, CourseTranslation] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            language = form.cleaned_data.get("language")
            if not language:
                continue
            if language in translations:
                raise ValidationError("Cada idioma deve aparecer apenas uma vez.")
            translations[language] = form.save(commit=False)

        if self.instance.status == Course.Status.PUBLISHED:
            errors = course_publication_errors(translations)
            if errors:
                raise ValidationError(errors)
