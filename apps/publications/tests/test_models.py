from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.publications.models import (
    Publication,
    PublicationAuthor,
    PublicationTranslation,
)
from apps.researchers.models import Researcher


def researcher(name: str = "Ana Silva") -> Researcher:
    return Researcher.objects.create(
        full_name=name,
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )


def complete_translations(publication: Publication) -> None:
    for language, title, abstract in (
        ("pt-br", "Computação na Amazônia", "Resumo em português"),
        ("en", "Computing in the Amazon", "Abstract in English"),
    ):
        PublicationTranslation.objects.create(
            publication=publication,
            language=language,
            title=title,
            abstract=abstract,
        )


@pytest.mark.django_db
def test_incomplete_draft_can_be_saved() -> None:
    publication = Publication.objects.create()
    translation = PublicationTranslation.objects.create(
        publication=publication,
        language="pt-br",
    )

    assert publication.status == Publication.Status.DRAFT
    assert publication.year is None
    assert translation.title == ""


@pytest.mark.django_db
def test_doi_is_normalized_validated_and_unique_case_insensitively() -> None:
    publication = Publication.objects.create(doi="https://doi.org/10.1000/ABC")
    assert publication.doi == "10.1000/abc"

    invalid = Publication(doi="identificador-invalido")
    with pytest.raises(ValidationError, match="DOI válido"):
        invalid.full_clean()

    with pytest.raises(IntegrityError), transaction.atomic():
        Publication.objects.create(doi="10.1000/ABC")


@pytest.mark.django_db
def test_publication_requires_year_venue_authors_and_complete_translations() -> None:
    publication = Publication.objects.create()
    with pytest.raises(ValidationError) as error:
        publication.validate_for_publication()
    assert "ano" in str(error.value)
    assert "periódico ou evento" in str(error.value)
    assert "autor" in str(error.value)
    assert "Português" in str(error.value)
    assert "English" in str(error.value)

    publication.year = 2026
    publication.venue = "Simpósio Brasileiro de Computação"
    publication.save()
    PublicationAuthor.objects.create(
        publication=publication,
        researcher=researcher(),
        display_order=1,
    )
    complete_translations(publication)
    publication.validate_for_publication()


@pytest.mark.django_db
def test_author_requires_one_identity_preserves_order_and_protects_researcher() -> None:
    publication = Publication.objects.create()
    person = researcher()

    with pytest.raises(ValidationError, match="nunca ambos"):
        PublicationAuthor(
            publication=publication,
            researcher=person,
            external_name="Autora externa",
        ).full_clean()

    PublicationAuthor.objects.create(
        publication=publication,
        external_name="Bruno Externo",
        display_order=2,
    )
    PublicationAuthor.objects.create(
        publication=publication,
        researcher=person,
        display_order=1,
    )

    assert [str(author) for author in publication.author_records.all()] == [
        "Ana Silva",
        "Bruno Externo",
    ]
    with pytest.raises(ProtectedError):
        person.delete()


@pytest.mark.django_db
def test_first_publication_date_is_preserved() -> None:
    publication = Publication.objects.create(
        status=Publication.Status.PUBLISHED,
        year=2026,
        venue="Evento",
    )
    first_publication = publication.published_at
    publication.status = Publication.Status.ARCHIVED
    publication.save()
    publication.status = Publication.Status.PUBLISHED
    publication.save()

    assert first_publication is not None
    assert timezone.now() - first_publication < timedelta(seconds=2)
    assert publication.published_at == first_publication


@pytest.mark.django_db
def test_translation_language_is_unique_per_publication() -> None:
    publication = Publication.objects.create()
    PublicationTranslation.objects.create(publication=publication, language="pt-br")

    with pytest.raises(IntegrityError), transaction.atomic():
        PublicationTranslation.objects.create(publication=publication, language="pt-br")
