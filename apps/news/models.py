from __future__ import annotations

from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .sanitizers import sanitize_rich_text
from .validators import validate_news_cover


def news_cover_upload_to(_instance: News, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"news/covers/{uuid4().hex}{extension}"


class NewsQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=News.Status.PUBLISHED, published_at__isnull=False)


class News(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicada"
        ARCHIVED = "archived", "Arquivada"

    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    cover = models.ImageField(
        "imagem de capa",
        upload_to=news_cover_upload_to,
        validators=[validate_news_cover],
        blank=True,
    )
    cover_credit = models.CharField("crédito da imagem", max_length=200, blank=True)
    published_at = models.DateTimeField("publicada em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criada por",
        related_name="news_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizada por",
        related_name="news_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = NewsQuerySet.as_manager()

    class Meta:
        verbose_name = "notícia"
        verbose_name_plural = "notícias"
        ordering = ("-published_at", "-pk")

    def __str__(self) -> str:
        if self.pk is None:
            return "Nova notícia"
        translation = next(
            (item for item in self.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Notícia #{self.pk}"

    def save(self, *args, **kwargs) -> None:
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def validate_for_publication(self) -> None:
        translations = {item.language: item for item in self.translations.all()}
        errors = publication_errors(self, translations)
        if errors:
            raise ValidationError(errors)


class NewsTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    news = models.ForeignKey(News, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("idioma", max_length=5, choices=Language)
    title = models.CharField("título", max_length=200, blank=True)
    slug = models.SlugField(max_length=220, null=True, blank=True)
    summary = models.TextField("resumo", max_length=400, blank=True)
    body_html = models.TextField("conteúdo", blank=True)
    cover_alt_text = models.CharField("texto alternativo da capa", max_length=200, blank=True)
    seo_title = models.CharField("título para SEO", max_length=70, blank=True)
    seo_description = models.CharField("descrição para SEO", max_length=160, blank=True)

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("news", "language"),
                name="unique_news_translation_language",
            ),
            models.UniqueConstraint(
                fields=("language", "slug"),
                condition=models.Q(slug__isnull=False),
                name="unique_news_translation_slug_per_language",
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


def publication_errors(
    news: News,
    translations: dict[str, NewsTranslation],
) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "title": "título",
        "slug": "slug",
        "summary": "resumo",
        "body_html": "conteúdo",
    }

    for language, label in NewsTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para publicar.")
            continue

        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")

        if news.cover and not translation.cover_alt_text.strip():
            errors.append(f"Preencha o texto alternativo da capa em {label}.")

    return errors
