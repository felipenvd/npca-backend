from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.projects.models import (
    Project,
    ProjectTeamMember,
    ProjectTranslation,
)
from apps.researchers.models import Researcher


def researcher(name: str = "Ana Silva") -> Researcher:
    return Researcher.objects.create(
        full_name=name,
        academic_category=Researcher.AcademicCategory.DOCTOR,
    )


def complete_translations(project: Project) -> None:
    for language, title in (("pt-br", "Projeto Amazônia"), ("en", "Amazon Project")):
        ProjectTranslation.objects.create(
            project=project,
            language=language,
            title=title,
            summary="Resumo completo",
            body_html="<p>Descrição completa</p>",
        )


@pytest.mark.django_db
def test_incomplete_draft_can_be_saved() -> None:
    project = Project.objects.create()
    translation = ProjectTranslation.objects.create(project=project, language="pt-br")

    assert project.status == Project.Status.DRAFT
    assert project.coordinator is None
    assert translation.slug is None


@pytest.mark.django_db
def test_translation_generates_slug_preserves_it_and_sanitizes_html() -> None:
    project = Project.objects.create()
    translation = ProjectTranslation.objects.create(
        project=project,
        language="pt-br",
        title="Ciência na Amazônia",
        body_html=(
            '<h2 onclick="alert(1)">Título</h2><script>alert(1)</script>'
            '<img src="x"><a href="javascript:alert(1)">link</a><strong>seguro</strong>'
        ),
    )
    original_slug = translation.slug
    translation.title = "Novo título"
    translation.save()

    assert original_slug == "ciencia-na-amazonia"
    assert translation.slug == original_slug
    assert "script" not in translation.body_html
    assert "onclick" not in translation.body_html
    assert "<img" not in translation.body_html
    assert "javascript:" not in translation.body_html
    assert "<h2>Título</h2>" in translation.body_html
    assert "<strong>seguro</strong>" in translation.body_html


@pytest.mark.django_db
def test_language_and_slug_constraints_are_enforced() -> None:
    first = Project.objects.create()
    second = Project.objects.create()
    ProjectTranslation.objects.create(
        project=first,
        language="pt-br",
        title="Primeiro",
        slug="mesmo-slug",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTranslation.objects.create(
            project=first,
            language="pt-br",
            slug="outro-slug",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTranslation.objects.create(
            project=second,
            language="pt-br",
            slug="mesmo-slug",
        )


@pytest.mark.django_db
def test_publication_requires_coordinator_start_and_complete_translations() -> None:
    project = Project.objects.create()
    with pytest.raises(ValidationError) as error:
        project.validate_for_publication()
    assert "coordenador" in str(error.value)
    assert "data de início" in str(error.value)
    assert "Português" in str(error.value)
    assert "English" in str(error.value)

    project.coordinator = researcher()
    project.start_date = date(2026, 1, 1)
    project.save()
    complete_translations(project)
    project.validate_for_publication()


@pytest.mark.django_db
def test_dates_and_completed_publication_are_validated() -> None:
    coordinator = researcher()
    project = Project(
        coordinator=coordinator,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 1, 31),
    )
    with pytest.raises(ValidationError, match="posterior"):
        project.full_clean()

    project.end_date = None
    project.status = Project.Status.PUBLISHED
    project.situation = Project.Situation.COMPLETED
    with pytest.raises(ValidationError, match="data de término"):
        project.full_clean()


@pytest.mark.django_db
def test_coordinator_cannot_be_a_team_member_and_related_researchers_are_protected() -> None:
    coordinator = researcher()
    member = researcher("Bruno Costa")
    project = Project.objects.create(coordinator=coordinator)
    membership = ProjectTeamMember(project=project, researcher=coordinator)
    with pytest.raises(ValidationError, match="coordenador"):
        membership.full_clean()

    ProjectTeamMember.objects.create(project=project, researcher=member)
    with pytest.raises(ProtectedError):
        coordinator.delete()
    with pytest.raises(ProtectedError):
        member.delete()


@pytest.mark.django_db
def test_first_publication_date_is_preserved() -> None:
    project = Project.objects.create(
        status=Project.Status.PUBLISHED,
        coordinator=researcher(),
        start_date=date(2026, 1, 1),
    )
    first_publication = project.published_at
    project.status = Project.Status.ARCHIVED
    project.save()
    project.status = Project.Status.PUBLISHED
    project.save()

    assert first_publication is not None
    assert timezone.now() - first_publication < timedelta(seconds=2)
    assert project.published_at == first_publication
