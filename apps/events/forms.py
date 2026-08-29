from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.widgets import UnfoldAdminSingleTimeWidget, UnfoldAdminURLInputWidget

from apps.core.sanitizers import sanitize_rich_text
from apps.core.widgets import EnhancedAdminDateWidget

from .models import Event, EventTranslation, event_publication_errors


class EventForm(forms.ModelForm):
    start_date = forms.DateField(
        label="Data de início *",
        required=False,
        widget=EnhancedAdminDateWidget(),
        help_text="Obrigatória para publicar. Use o formato dd/mm/aaaa.",
    )
    end_date = forms.DateField(
        label="Data de término *",
        required=False,
        widget=EnhancedAdminDateWidget(),
        help_text="Obrigatória para publicar. Use o formato dd/mm/aaaa.",
    )
    start_time = forms.TimeField(
        label="Hora de início",
        required=False,
        widget=UnfoldAdminSingleTimeWidget(attrs={"placeholder": "hh:mm"}),
        help_text="Obrigatória para publicar quando não for um evento de dia inteiro.",
    )
    end_time = forms.TimeField(
        label="Hora de término",
        required=False,
        widget=UnfoldAdminSingleTimeWidget(attrs={"placeholder": "hh:mm"}),
        help_text="Obrigatória para publicar quando não for um evento de dia inteiro.",
    )
    online_url = forms.URLField(
        label="URL de acesso online",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )
    registration_url = forms.URLField(
        label="URL externa de inscrição",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )

    class Meta:
        model = Event
        fields = (
            "status",
            "schedule_status",
            "event_type",
            "modality",
            "start_date",
            "end_date",
            "is_all_day",
            "start_time",
            "end_time",
            "cover",
            "cover_credit",
            "online_url",
            "registration_url",
            "display_order",
        )
        labels = {
            "event_type": "Tipo *",
            "modality": "Modalidade *",
        }
        help_texts = {
            "event_type": "Obrigatório para publicar.",
            "modality": "Obrigatória para publicar.",
            "is_all_day": "Marque para eventos sem horário específico.",
            "cover": "Opcional. Use uma imagem JPEG, PNG ou WebP de até 5 MiB.",
            "cover_credit": "Opcional. Informe a autoria ou a fonte da imagem.",
            "online_url": "Obrigatória para eventos online e híbridos.",
            "registration_url": "Opcional. A inscrição continuará em um serviço externo.",
            "display_order": "Desempata eventos com a mesma data e horário.",
        }

    def clean(self) -> dict:
        cleaned_data = super().clean()
        if cleaned_data.get("is_all_day"):
            cleaned_data["start_time"] = None
            cleaned_data["end_time"] = None
        return cleaned_data


class EventTranslationForm(forms.ModelForm):
    class Meta:
        model = EventTranslation
        fields = (
            "language",
            "title",
            "slug",
            "summary",
            "body_html",
            "location_name",
            "location_address",
            "cover_alt_text",
            "seo_title",
            "seo_description",
        )
        widgets = {"body_html": WysiwygWidget()}
        labels = {
            "title": "Título *",
            "summary": "Resumo *",
            "body_html": "Descrição *",
        }
        help_texts = {
            "title": "Obrigatório para publicar.",
            "slug": (
                "Gerado automaticamente a partir do título quando deixado em branco. "
                "Depois de publicado, altere somente se também for atualizar a URL."
            ),
            "summary": "Obrigatório para publicar.",
            "body_html": "Obrigatória para publicar.",
            "location_name": "Obrigatório para eventos presenciais e híbridos.",
            "location_address": "Opcional. Informe endereço ou instruções de chegada.",
            "cover_alt_text": (
                "Descreva a imagem quando ela transmitir informação relevante. "
                "Deixe vazio quando for apenas decorativa."
            ),
            "seo_title": "Opcional. Quando vazio, o título do evento será usado.",
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
        cleaned_data["slug"] = slug or (slugify(title) if title else None)
        cleaned_data["body_html"] = sanitize_rich_text(cleaned_data.get("body_html") or "")
        return cleaned_data


class EventTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in EventTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, EventTranslation] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            language = form.cleaned_data.get("language")
            if not language:
                continue
            if language in translations:
                raise ValidationError("Cada idioma deve aparecer apenas uma vez.")
            translations[language] = form.save(commit=False)

        if self.instance.status == Event.Status.PUBLISHED:
            errors = event_publication_errors(
                translations,
                modality=self.instance.modality,
            )
            if errors:
                raise ValidationError(errors)
