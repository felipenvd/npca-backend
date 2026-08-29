import pytest
from django.forms import inlineformset_factory
from unfold.widgets import UnfoldAdminURLInputWidget

from apps.researchers.forms import (
    ResearcherForm,
    ResearcherTranslationForm,
    ResearcherTranslationInlineFormSet,
)
from apps.researchers.models import Researcher, ResearcherTranslation


def translation_formset(data: dict, instance: Researcher):
    formset_class = inlineformset_factory(
        Researcher,
        ResearcherTranslation,
        form=ResearcherTranslationForm,
        formset=ResearcherTranslationInlineFormSet,
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
def test_inactive_researcher_accepts_incomplete_translations() -> None:
    researcher = Researcher(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=False,
    )
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-role": "Professora",
        "translations-1-language": "en",
    }

    formset = translation_formset(data, researcher)

    assert formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_activation_requires_two_complete_translations() -> None:
    researcher = Researcher(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=True,
    )
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-role": "Professora",
        "translations-0-research_area": "Inteligência Artificial",
        "translations-0-biography_html": "<p>Biografia</p>",
        "translations-1-language": "en",
        "translations-1-role": "",
    }

    formset = translation_formset(data, researcher)

    assert not formset.is_valid()
    assert "Preencha função na tradução em English" in str(formset.non_form_errors())


@pytest.mark.django_db
def test_complete_bilingual_researcher_generates_slugs() -> None:
    researcher = Researcher(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=True,
    )
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-slug": "",
        "translations-0-role": "Professora",
        "translations-0-research_area": "Inteligência Artificial",
        "translations-0-biography_html": "<p>Biografia</p>",
        "translations-1-language": "en",
        "translations-1-slug": "",
        "translations-1-role": "Professor",
        "translations-1-research_area": "Artificial Intelligence",
        "translations-1-biography_html": "<p>Biography</p>",
    }

    formset = translation_formset(data, researcher)

    assert formset.is_valid(), (formset.errors, formset.non_form_errors())
    assert formset.forms[0].cleaned_data["slug"] == "ana-silva"
    assert formset.forms[1].cleaned_data["slug"] == "ana-silva"


@pytest.mark.django_db
def test_active_researcher_with_photo_requires_alt_text_in_both_languages() -> None:
    researcher = Researcher(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        is_active=True,
    )
    researcher.photo.name = "researchers/photos/example.webp"
    data = {
        **management_data(),
        "translations-0-language": "pt-br",
        "translations-0-role": "Professora",
        "translations-0-research_area": "Inteligência Artificial",
        "translations-0-biography_html": "<p>Biografia</p>",
        "translations-0-photo_alt_text": "Retrato de Ana Silva",
        "translations-1-language": "en",
        "translations-1-role": "Professor",
        "translations-1-research_area": "Artificial Intelligence",
        "translations-1-biography_html": "<p>Biography</p>",
    }

    formset = translation_formset(data, researcher)

    assert not formset.is_valid()
    assert "texto alternativo da foto em English" in str(formset.non_form_errors())


def test_translation_form_explains_activation_requirements() -> None:
    form = ResearcherTranslationForm()

    for field_name in ("role", "research_area", "biography_html"):
        field = form.fields[field_name]
        assert field.label.endswith(" *")
        assert field.help_text == "Obrigatório para ativar."
        assert field.required is False

    assert "Gerado automaticamente" in form.fields["slug"].help_text
    assert "quando houver foto" in form.fields["photo_alt_text"].help_text
    assert form.fields["seo_title"].help_text.startswith("Opcional.")
    assert form.fields["seo_description"].help_text.startswith("Opcional.")


def test_researcher_url_fields_use_unfold_widgets() -> None:
    form = ResearcherForm()

    for field_name in ("lattes_url", "orcid_url", "linkedin_url"):
        widget = form.fields[field_name].widget
        assert isinstance(widget, UnfoldAdminURLInputWidget)
        assert "border" in widget.attrs["class"].split()
        assert "w-full" in widget.attrs["class"].split()
