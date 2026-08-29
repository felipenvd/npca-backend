from __future__ import annotations

import re
from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.projects.models import Project
from apps.researchers.models import Researcher

from .validators import validate_publication_file

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
DOI_PREFIX_PATTERN = re.compile(
    r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)",
    re.IGNORECASE,
)


def publication_file_upload_to(_instance: Publication, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"publications/files/{uuid4().hex}{extension}"


def normalize_doi(value: str) -> str:
    return DOI_PREFIX_PATTERN.sub("", value.strip()).strip().lower()


class PublicationQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Publication.Status.PUBLISHED,
            published_at__isnull=False,
        )


class Publication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Arquivado"

    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    year = models.PositiveSmallIntegerField(
        "ano",
        validators=[MinValueValidator(1000)],
        null=True,
        blank=True,
    )
    venue = models.CharField("periódico ou evento", max_length=300, blank=True)
    doi = models.CharField("DOI", max_length=255, blank=True)
    external_url = models.URLField("URL externa", max_length=500, blank=True)
    document = models.FileField(
        "arquivo PDF",
        upload_to=publication_file_upload_to,
        validators=[validate_publication_file],
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        verbose_name="projeto relacionado",
        related_name="publications",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    authors = models.ManyToManyField(
        Researcher,
        verbose_name="autores cadastrados",
        related_name="publications",
        through="PublicationAuthor",
        blank=True,
    )
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)
    published_at = models.DateTimeField("publicado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        related_name="publications_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        related_name="publications_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = PublicationQuerySet.as_manager()

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        ordering = ("-year", "display_order", "pk")
        constraints = [
            models.UniqueConstraint(
                Lower("doi"),
                condition=~models.Q(doi=""),
                name="unique_publication_doi_case_insensitive",
            )
        ]

    def __str__(self) -> str:
        if self.pk is None:
            return "Nova publicação"
        translation = next(
            (item for item in self.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Publicação #{self.pk}"

    def save(self, *args, **kwargs) -> None:
        self.doi = normalize_doi(self.doi)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.doi = normalize_doi(self.doi)
        errors: dict[str, str] = {}
        if self.doi and not DOI_PATTERN.fullmatch(self.doi):
            errors["doi"] = "Informe um DOI válido, por exemplo 10.1000/exemplo."
        if self.year and self.year > timezone.localdate().year + 1:
            errors["year"] = "O ano não pode ser posterior ao próximo ano."
        if self.status == self.Status.PUBLISHED:
            if self.year is None:
                errors["year"] = "Informe o ano antes de publicar."
            if not self.venue.strip():
                errors["venue"] = "Informe o periódico ou evento antes de publicar."
        if errors:
            raise ValidationError(errors)

    def validate_for_publication(self) -> None:
        errors = publication_errors(
            {translation.language: translation for translation in self.translations.all()}
        )
        if self.year is None:
            errors.append("Informe o ano antes de publicar.")
        if not self.venue.strip():
            errors.append("Informe o periódico ou evento antes de publicar.")
        if self.pk and not self.author_records.exists():
            errors.append("Informe pelo menos um autor antes de publicar.")
        if errors:
            raise ValidationError(errors)


class PublicationTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    publication = models.ForeignKey(
        Publication,
        related_name="translations",
        on_delete=models.CASCADE,
    )
    language = models.CharField("idioma", max_length=5, choices=Language)
    title = models.CharField("título", max_length=500, blank=True)
    abstract = models.TextField("resumo", blank=True)
    seo_title = models.CharField("título para SEO", max_length=70, blank=True)
    seo_description = models.CharField("descrição para SEO", max_length=160, blank=True)

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("publication", "language"),
                name="unique_publication_translation_language",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_language_display()}: {self.title or 'sem título'}"


class PublicationAuthor(models.Model):
    publication = models.ForeignKey(
        Publication,
        related_name="author_records",
        on_delete=models.CASCADE,
    )
    researcher = models.ForeignKey(
        Researcher,
        verbose_name="pesquisador cadastrado",
        related_name="publication_authorships",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    external_name = models.CharField("nome do autor externo", max_length=200, blank=True)
    display_order = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autores"
        ordering = ("display_order", "pk")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(researcher__isnull=False, external_name="")
                    | (models.Q(researcher__isnull=True) & ~models.Q(external_name=""))
                ),
                name="publication_author_has_exactly_one_identity",
            ),
            models.UniqueConstraint(
                fields=("publication", "researcher"),
                condition=models.Q(researcher__isnull=False),
                name="unique_publication_researcher_author",
            ),
            models.UniqueConstraint(
                fields=("publication", "display_order"),
                name="unique_publication_author_order",
            ),
        ]

    def __str__(self) -> str:
        return self.researcher.full_name if self.researcher else self.external_name

    def clean(self) -> None:
        super().clean()
        self.external_name = self.external_name.strip()
        if bool(self.researcher_id) == bool(self.external_name):
            raise ValidationError(
                "Selecione um pesquisador cadastrado ou informe um autor externo, nunca ambos."
            )


def publication_errors(translations: dict[str, PublicationTranslation]) -> list[str]:
    errors: list[str] = []
    required_fields = {"title": "título", "abstract": "resumo"}
    for language, label in PublicationTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para publicar.")
            continue
        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")
    return errors
