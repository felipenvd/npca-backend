from __future__ import annotations

from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import validate_course_cover, validate_https_url


def course_cover_upload_to(_instance: Course, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"courses/covers/{uuid4().hex}{extension}"


class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Course.Status.PUBLISHED,
            published_at__isnull=False,
        )


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Arquivado"

    class CourseType(models.TextChoices):
        CHANNEL = "channel", "Canal"
        COURSE = "course", "Curso"
        PLAYLIST = "playlist", "Playlist"
        TUTORIAL = "tutorial", "Tutorial"
        RECORDED_LIVE = "recorded_live", "Live gravada"
        OTHER = "other", "Outro"

    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    course_type = models.CharField(
        "tipo",
        max_length=20,
        choices=CourseType,
        blank=True,
    )
    external_url = models.URLField(
        "URL externa",
        max_length=500,
        validators=[validate_https_url],
        blank=True,
    )
    cover = models.ImageField(
        "imagem de divulgação",
        upload_to=course_cover_upload_to,
        validators=[validate_course_cover],
        blank=True,
    )
    cover_credit = models.CharField("crédito da imagem", max_length=200, blank=True)
    is_featured = models.BooleanField("destaque na página inicial", default=False)
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)
    published_at = models.DateTimeField("publicado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        related_name="courses_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        related_name="courses_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = CourseQuerySet.as_manager()

    class Meta:
        verbose_name = "curso e tutorial"
        verbose_name_plural = "cursos e tutoriais"
        ordering = ("-is_featured", "display_order", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(external_url="") | models.Q(external_url__startswith="https://"),
                name="course_external_url_is_https",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="published")
                | (~models.Q(course_type="") & ~models.Q(external_url="")),
                name="published_course_has_type_and_url",
            ),
        ]

    def __str__(self) -> str:
        if self.pk is None:
            return "Novo curso ou tutorial"
        translation = next(
            (item for item in self.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Curso #{self.pk}"

    def save(self, *args, **kwargs) -> None:
        self.external_url = self.external_url.strip()
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.external_url = self.external_url.strip()
        errors: dict[str, str] = {}
        if self.status == self.Status.PUBLISHED:
            if not self.course_type:
                errors["course_type"] = "Informe o tipo antes de publicar."
            if not self.external_url:
                errors["external_url"] = "Informe a URL externa antes de publicar."
        if errors:
            raise ValidationError(errors)

    def validate_for_publication(self) -> None:
        errors = course_publication_errors(
            {translation.language: translation for translation in self.translations.all()}
        )
        if not self.course_type:
            errors.append("Informe o tipo antes de publicar.")
        if not self.external_url:
            errors.append("Informe a URL externa antes de publicar.")
        else:
            try:
                validate_https_url(self.external_url)
            except ValidationError as error:
                errors.extend(error.messages)
        if errors:
            raise ValidationError(errors)


class CourseTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    course = models.ForeignKey(
        Course,
        related_name="translations",
        on_delete=models.CASCADE,
    )
    language = models.CharField("idioma", max_length=5, choices=Language)
    title = models.CharField("título", max_length=300, blank=True)
    summary = models.TextField("resumo", blank=True)
    cover_alt_text = models.CharField(
        "texto alternativo da imagem",
        max_length=250,
        blank=True,
    )

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("course", "language"),
                name="unique_course_translation_language",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_language_display()}: {self.title or 'sem título'}"


def course_publication_errors(translations: dict[str, CourseTranslation]) -> list[str]:
    errors: list[str] = []
    required_fields = {"title": "título", "summary": "resumo"}
    for language, label in CourseTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para publicar.")
            continue
        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")
    return errors
