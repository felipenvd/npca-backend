from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.widgets import UnfoldAdminTextInputWidget, UnfoldAdminURLInputWidget

from apps.core.sanitizers import sanitize_rich_text

from .models import Project, ProjectTeamMember, ProjectTranslation, publication_errors


class ProjectForm(forms.ModelForm):
    start_date = forms.DateField(
        label="Data de início *",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=UnfoldAdminTextInputWidget(attrs={"type": "date"}),
        help_text=(
            "Obrigatória para publicar. Use o seletor ou informe a data no formato "
            "exibido pelo navegador."
        ),
    )
    end_date = forms.DateField(
        label="Data de término",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=UnfoldAdminTextInputWidget(attrs={"type": "date"}),
        help_text=(
            "Obrigatória para publicar projetos concluídos. Use o seletor ou informe "
            "a data no formato exibido pelo navegador."
        ),
    )
    website_url = forms.URLField(
        label="Site do projeto",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )
    repository_url = forms.URLField(
        label="Repositório",
        required=False,
        assume_scheme="https",
        widget=UnfoldAdminURLInputWidget(),
    )

    class Meta:
        model = Project
        fields = (
            "status",
            "situation",
            "coordinator",
            "start_date",
            "end_date",
            "cover",
            "cover_credit",
            "funding",
            "partners",
            "website_url",
            "repository_url",
            "is_featured",
            "display_order",
        )
        labels = {"coordinator": "Coordenador *"}
        help_texts = {
            "coordinator": "Obrigatório para publicar.",
            "display_order": "Define a posição entre projetos da mesma situação.",
            "is_featured": "Projetos destacados podem aparecer na página inicial.",
        }


class ProjectTranslationForm(forms.ModelForm):
    class Meta:
        model = ProjectTranslation
        fields = (
            "language",
            "title",
            "slug",
            "summary",
            "body_html",
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
            "seo_title": "Opcional. Quando vazio, o título do projeto será usado.",
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


class ProjectTranslationInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            existing = {form.instance.language for form in self.initial_forms}
            missing = [
                language
                for language, _label in ProjectTranslation.Language.choices
                if language not in existing
            ]
            for form, language in zip(self.extra_forms, missing, strict=False):
                form.initial["language"] = language

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        translations: dict[str, ProjectTranslation] = {}
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

        if self.instance.status == Project.Status.PUBLISHED:
            errors = publication_errors(translations)
            if errors:
                raise ValidationError(errors)


class ProjectTeamMemberInlineFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        seen: set[int] = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            researcher = form.cleaned_data.get("researcher")
            if researcher is None:
                continue
            if researcher.pk in seen:
                raise ValidationError("Cada pesquisador deve aparecer apenas uma vez na equipe.")
            if researcher.pk == self.instance.coordinator_id:
                raise ValidationError("O coordenador não pode aparecer também na equipe.")
            seen.add(researcher.pk)


class ProjectTeamMemberForm(forms.ModelForm):
    class Meta:
        model = ProjectTeamMember
        fields = ("researcher",)
