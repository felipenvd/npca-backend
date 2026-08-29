from __future__ import annotations

from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.sanitizers import sanitize_rich_text
from apps.researchers.models import Researcher

from .validators import validate_project_cover


def project_cover_upload_to(_instance: Project, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"projects/covers/{uuid4().hex}{extension}"


def project_situation_ordering(field_name: str = "situation") -> models.Case:
    priorities = (
        ("ongoing", 0),
        ("planned", 1),
        ("completed", 2),
    )
    return models.Case(
        *(
            models.When(**{field_name: value}, then=models.Value(priority))
            for value, priority in priorities
        ),
        default=models.Value(len(priorities)),
        output_field=models.IntegerField(),
    )


class ProjectQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Project.Status.PUBLISHED,
            published_at__isnull=False,
        )


class Project(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Arquivado"

    class Situation(models.TextChoices):
        PLANNED = "planned", "Planejado"
        ONGOING = "ongoing", "Em andamento"
        COMPLETED = "completed", "Concluído"

    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    situation = models.CharField(
        "situação",
        max_length=10,
        choices=Situation,
        default=Situation.PLANNED,
    )
    cover = models.ImageField(
        "imagem de capa",
        upload_to=project_cover_upload_to,
        validators=[validate_project_cover],
        blank=True,
    )
    cover_credit = models.CharField("crédito da imagem", max_length=200, blank=True)
    start_date = models.DateField("data de início", null=True, blank=True)
    end_date = models.DateField("data de término", null=True, blank=True)
    coordinator = models.ForeignKey(
        Researcher,
        verbose_name="coordenador",
        related_name="coordinated_projects",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    team = models.ManyToManyField(
        Researcher,
        verbose_name="equipe",
        related_name="projects",
        through="ProjectTeamMember",
        blank=True,
    )
    funding = models.CharField("financiamento", max_length=300, blank=True)
    partners = models.TextField(
        "parceiros",
        blank=True,
        help_text="Informe um parceiro por linha.",
    )
    website_url = models.URLField("site do projeto", max_length=500, blank=True)
    repository_url = models.URLField("repositório", max_length=500, blank=True)
    is_featured = models.BooleanField("destaque", default=False)
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)
    published_at = models.DateTimeField("publicado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        related_name="projects_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        related_name="projects_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = ProjectQuerySet.as_manager()

    class Meta:
        verbose_name = "projeto"
        verbose_name_plural = "projetos"
        ordering = (project_situation_ordering(), "display_order", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="project_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="published") | models.Q(coordinator__isnull=False),
                name="published_project_has_coordinator",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="published") | models.Q(start_date__isnull=False),
                name="published_project_has_start_date",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    status="published",
                    situation="completed",
                )
                | models.Q(end_date__isnull=False),
                name="completed_published_project_has_end",
            ),
        ]

    def __str__(self) -> str:
        if self.pk is None:
            return "Novo projeto"
        translation = next(
            (item for item in self.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Projeto #{self.pk}"

    def save(self, *args, **kwargs) -> None:
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "A data de término deve ser igual ou posterior ao início."
        if self.status == self.Status.PUBLISHED:
            if self.coordinator_id is None:
                errors["coordinator"] = "Informe o coordenador antes de publicar."
            if self.start_date is None:
                errors["start_date"] = "Informe a data de início antes de publicar."
            if self.situation == self.Situation.COMPLETED and self.end_date is None:
                errors["end_date"] = "Projetos concluídos precisam de uma data de término."
        if errors:
            raise ValidationError(errors)

    def validate_for_publication(self) -> None:
        errors = publication_errors(
            {translation.language: translation for translation in self.translations.all()}
        )
        if self.coordinator_id is None:
            errors.append("Informe o coordenador antes de publicar.")
        if self.start_date is None:
            errors.append("Informe a data de início antes de publicar.")
        if self.situation == self.Situation.COMPLETED and self.end_date is None:
            errors.append("Projetos concluídos precisam de uma data de término.")
        if self.pk and self.coordinator_id and self.team.filter(pk=self.coordinator_id).exists():
            errors.append("O coordenador não pode aparecer também na equipe.")
        if errors:
            raise ValidationError(errors)


class ProjectTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    project = models.ForeignKey(Project, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("idioma", max_length=5, choices=Language)
    title = models.CharField("título", max_length=200, blank=True)
    slug = models.SlugField(max_length=220, null=True, blank=True)
    summary = models.TextField("resumo", max_length=400, blank=True)
    body_html = models.TextField("descrição", blank=True)
    seo_title = models.CharField("título para SEO", max_length=70, blank=True)
    seo_description = models.CharField("descrição para SEO", max_length=160, blank=True)

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("project", "language"),
                name="unique_project_translation_language",
            ),
            models.UniqueConstraint(
                fields=("language", "slug"),
                condition=models.Q(slug__isnull=False),
                name="unique_project_translation_slug_per_language",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_language_display()}: {self.title or 'sem título'}"

    def save(self, *args, **kwargs) -> None:
        self.body_html = sanitize_rich_text(self.body_html)
        self.slug = self.slug or (slugify(self.title) if self.title else None)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.body_html = sanitize_rich_text(self.body_html)
        self.slug = self.slug or (slugify(self.title) if self.title else None)


class ProjectTeamMember(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="team_memberships",
        on_delete=models.CASCADE,
    )
    researcher = models.ForeignKey(
        Researcher,
        verbose_name="pesquisador",
        related_name="project_memberships",
        on_delete=models.PROTECT,
    )

    class Meta:
        verbose_name = "integrante da equipe"
        verbose_name_plural = "integrantes da equipe"
        constraints = [
            models.UniqueConstraint(
                fields=("project", "researcher"),
                name="unique_project_team_member",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project} — {self.researcher}"

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.researcher_id:
            coordinator_id = (
                Project.objects.filter(pk=self.project_id)
                .values_list("coordinator_id", flat=True)
                .first()
            )
            if coordinator_id == self.researcher_id:
                raise ValidationError(
                    {"researcher": "O coordenador não pode aparecer também na equipe."}
                )


def publication_errors(translations: dict[str, ProjectTranslation]) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "title": "título",
        "slug": "slug",
        "summary": "resumo",
        "body_html": "descrição",
    }
    for language, label in ProjectTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para publicar.")
            continue
        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")
    return errors
