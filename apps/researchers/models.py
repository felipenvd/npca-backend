from __future__ import annotations

from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils.text import slugify

from apps.core.sanitizers import sanitize_rich_text

from .validators import validate_researcher_photo


def researcher_photo_upload_to(_instance: Researcher, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"researchers/photos/{uuid4().hex}{extension}"


class ResearcherQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Researcher(models.Model):
    full_name = models.CharField("nome completo", max_length=200)
    photo = models.ImageField(
        "foto",
        upload_to=researcher_photo_upload_to,
        validators=[validate_researcher_photo],
        blank=True,
    )
    public_email = models.EmailField("e-mail institucional ou profissional", blank=True)
    lattes_url = models.URLField("Currículo Lattes", max_length=500, blank=True)
    orcid_url = models.URLField("ORCID", max_length=500, blank=True)
    linkedin_url = models.URLField("LinkedIn", max_length=500, blank=True)
    is_active = models.BooleanField("ativo", default=False)
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        related_name="researchers_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        related_name="researchers_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = ResearcherQuerySet.as_manager()

    class Meta:
        verbose_name = "pesquisador"
        verbose_name_plural = "pesquisadores"
        ordering = ("display_order", "full_name", "pk")

    def __str__(self) -> str:
        return self.full_name

    def validate_for_activation(self) -> None:
        translations = {item.language: item for item in self.translations.all()}
        errors = activation_errors(self, translations)
        if errors:
            raise ValidationError(errors)


class ResearcherTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    researcher = models.ForeignKey(
        Researcher,
        related_name="translations",
        on_delete=models.CASCADE,
    )
    language = models.CharField("idioma", max_length=5, choices=Language)
    slug = models.SlugField(max_length=220, null=True, blank=True)
    role = models.CharField("função", max_length=200, blank=True)
    research_area = models.CharField("área de pesquisa", max_length=200, blank=True)
    biography_html = models.TextField("biografia", blank=True)
    photo_alt_text = models.CharField("texto alternativo da foto", max_length=200, blank=True)
    seo_title = models.CharField("título para SEO", max_length=70, blank=True)
    seo_description = models.CharField("descrição para SEO", max_length=160, blank=True)

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("researcher", "language"),
                name="unique_researcher_translation_language",
            ),
            models.UniqueConstraint(
                fields=("language", "slug"),
                condition=models.Q(slug__isnull=False),
                name="unique_researcher_translation_slug_per_language",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_language_display()}: {self.researcher.full_name}"

    def save(self, *args, **kwargs) -> None:
        self.biography_html = sanitize_rich_text(self.biography_html)
        self.slug = self.slug or self.default_slug()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.biography_html = sanitize_rich_text(self.biography_html)
        self.slug = self.slug or self.default_slug()

    def default_slug(self) -> str | None:
        try:
            full_name = self.researcher.full_name
        except AttributeError, ObjectDoesNotExist:
            return None
        return slugify(full_name) if full_name else None


def activation_errors(
    researcher: Researcher,
    translations: dict[str, ResearcherTranslation],
) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "slug": "slug",
        "role": "função",
        "research_area": "área de pesquisa",
        "biography_html": "biografia",
    }

    for language, label in ResearcherTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para ativar.")
            continue

        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")

        if researcher.photo and not translation.photo_alt_text.strip():
            errors.append(f"Preencha o texto alternativo da foto em {label}.")

    return errors
