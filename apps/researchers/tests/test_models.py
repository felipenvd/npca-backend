import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.researchers.models import Researcher, ResearcherTranslation


@pytest.mark.django_db
def test_inactive_researcher_accepts_incomplete_translation() -> None:
    researcher = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    translation = ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
    )

    assert researcher.is_active is False
    assert translation.slug == "ana-silva"


@pytest.mark.django_db
def test_translation_generates_stable_slug_and_sanitizes_biography() -> None:
    researcher = Researcher.objects.create(
        full_name="Ágata Ciência",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    translation = ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
        biography_html=(
            '<h2 onclick="alert(1)">Biografia</h2><script>alert(1)</script>'
            '<a href="javascript:alert(1)">link</a><strong>seguro</strong>'
        ),
    )

    assert translation.slug == "agata-ciencia"
    assert "script" not in translation.biography_html
    assert "onclick" not in translation.biography_html
    assert "javascript:" not in translation.biography_html
    assert "<h2>Biografia</h2>" in translation.biography_html
    assert "<strong>seguro</strong>" in translation.biography_html

    researcher.full_name = "Ágata Computação"
    researcher.save()
    translation.save()

    assert translation.slug == "agata-ciencia"


@pytest.mark.django_db
def test_language_and_slug_constraints_are_enforced() -> None:
    first = Researcher.objects.create(
        full_name="Primeira Pessoa",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    second = Researcher.objects.create(
        full_name="Segunda Pessoa",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    ResearcherTranslation.objects.create(
        researcher=first,
        language="pt-br",
        slug="mesmo-slug",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ResearcherTranslation.objects.create(
            researcher=first,
            language="pt-br",
            slug="outro-slug",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        ResearcherTranslation.objects.create(
            researcher=second,
            language="pt-br",
            slug="mesmo-slug",
        )


@pytest.mark.django_db
def test_activation_requires_complete_bilingual_content_and_photo_alt_text() -> None:
    researcher = Researcher.objects.create(
        full_name="Ana Silva",
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )
    ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
        role="Professora",
        research_area="Inteligência Artificial",
        biography_html="<p>Biografia</p>",
    )

    with pytest.raises(ValidationError, match="English"):
        researcher.validate_for_activation()

    ResearcherTranslation.objects.create(
        researcher=researcher,
        language="en",
        role="Professor",
        research_area="Artificial Intelligence",
        biography_html="<p>Biography</p>",
    )
    researcher.validate_for_activation()

    researcher.photo.name = "researchers/photos/example.webp"
    with pytest.raises(ValidationError, match="texto alternativo da foto"):
        researcher.validate_for_activation()


@pytest.mark.django_db
def test_academic_category_is_constrained_and_controls_default_ordering() -> None:
    master = Researcher.objects.create(
        full_name="Ana Mestranda",
        academic_category=Researcher.AcademicCategory.MASTERS_STUDENT,
        display_order=1,
    )
    second_doctor = Researcher.objects.create(
        full_name="Bruno Doutor",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        display_order=2,
    )
    first_doctor = Researcher.objects.create(
        full_name="Ana Doutora",
        academic_category=Researcher.AcademicCategory.DOCTOR,
        display_order=1,
    )

    assert list(Researcher.objects.all()) == [first_doctor, second_doctor, master]

    with pytest.raises(IntegrityError), transaction.atomic():
        Researcher.objects.create(
            full_name="Categoria inválida",
            academic_category="invalid",
        )
