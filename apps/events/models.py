from __future__ import annotations

from datetime import datetime
from pathlib import PurePath
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.sanitizers import sanitize_rich_text

from .validators import validate_event_cover


def event_cover_upload_to(_instance: Event, filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return f"events/covers/{uuid4().hex}{extension}"


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Event.Status.PUBLISHED,
            published_at__isnull=False,
        )


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Arquivado"

    class ScheduleStatus(models.TextChoices):
        SCHEDULED = "scheduled", "Agendado"
        POSTPONED = "postponed", "Adiado"
        CANCELED = "canceled", "Cancelado"

    class EventType(models.TextChoices):
        LECTURE = "lecture", "Palestra"
        SEMINAR = "seminar", "Seminário"
        WORKSHOP = "workshop", "Workshop"
        COURSE = "course", "Curso"
        DEFENSE = "defense", "Defesa"
        CONFERENCE = "conference", "Conferência"
        MEETUP = "meetup", "Encontro"
        OTHER = "other", "Outro"

    class Modality(models.TextChoices):
        IN_PERSON = "in_person", "Presencial"
        ONLINE = "online", "Online"
        HYBRID = "hybrid", "Híbrido"

    class TemporalState(models.TextChoices):
        UPCOMING = "upcoming", "Próximo"
        ONGOING = "ongoing", "Em andamento"
        PAST = "past", "Encerrado"

    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    schedule_status = models.CharField(
        "situação",
        max_length=10,
        choices=ScheduleStatus,
        default=ScheduleStatus.SCHEDULED,
    )
    event_type = models.CharField(
        "tipo",
        max_length=20,
        choices=EventType,
        blank=True,
    )
    modality = models.CharField(
        "modalidade",
        max_length=10,
        choices=Modality,
        blank=True,
    )
    start_date = models.DateField("data de início", null=True, blank=True)
    end_date = models.DateField("data de término", null=True, blank=True)
    is_all_day = models.BooleanField("evento de dia inteiro", default=False)
    start_time = models.TimeField("hora de início", null=True, blank=True)
    end_time = models.TimeField("hora de término", null=True, blank=True)
    cover = models.ImageField(
        "imagem de divulgação",
        upload_to=event_cover_upload_to,
        validators=[validate_event_cover],
        blank=True,
    )
    cover_credit = models.CharField("crédito da imagem", max_length=200, blank=True)
    online_url = models.URLField("URL de acesso online", max_length=500, blank=True)
    registration_url = models.URLField("URL externa de inscrição", max_length=500, blank=True)
    display_order = models.PositiveIntegerField("ordem de exibição", default=0)
    published_at = models.DateTimeField("publicado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        related_name="events_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        related_name="events_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        ordering = ("start_date", "start_time", "display_order", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="event_end_date_not_before_start",
            ),
            models.CheckConstraint(
                condition=models.Q(is_all_day=False)
                | (models.Q(start_time__isnull=True) & models.Q(end_time__isnull=True)),
                name="all_day_event_has_no_times",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="published")
                | (
                    models.Q(start_date__isnull=False)
                    & models.Q(end_date__isnull=False)
                    & ~models.Q(event_type="")
                    & ~models.Q(modality="")
                ),
                name="published_event_has_core_schedule",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    status="published",
                    modality__in=("online", "hybrid"),
                )
                | ~models.Q(online_url=""),
                name="published_online_event_has_url",
            ),
        ]

    def __str__(self) -> str:
        if self.pk is None:
            return "Novo evento"
        translation = next(
            (item for item in self.translations.all() if item.language == "pt-br"),
            None,
        )
        return translation.title if translation and translation.title else f"Evento #{self.pk}"

    def save(self, *args, **kwargs) -> None:
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "A data de término deve ser igual ou posterior ao início."
        if self.is_all_day and (self.start_time or self.end_time):
            errors["is_all_day"] = "Eventos de dia inteiro não devem informar horários."
        if (
            not self.is_all_day
            and self.start_date
            and self.end_date
            and self.start_time
            and self.end_time
            and datetime.combine(self.end_date, self.end_time)
            <= datetime.combine(self.start_date, self.start_time)
        ):
            errors["end_time"] = "O término deve ser posterior ao início."
        if self.status == self.Status.PUBLISHED:
            if not self.event_type:
                errors["event_type"] = "Informe o tipo antes de publicar."
            if not self.modality:
                errors["modality"] = "Informe a modalidade antes de publicar."
            if self.start_date is None:
                errors["start_date"] = "Informe a data de início antes de publicar."
            if self.end_date is None:
                errors["end_date"] = "Informe a data de término antes de publicar."
            if not self.is_all_day:
                if self.start_time is None:
                    errors["start_time"] = "Informe a hora de início antes de publicar."
                if self.end_time is None:
                    errors["end_time"] = "Informe a hora de término antes de publicar."
            if (
                self.modality in {self.Modality.ONLINE, self.Modality.HYBRID}
                and not (self.online_url or "").strip()
            ):
                errors["online_url"] = "Informe a URL de acesso para esta modalidade."
        if errors:
            raise ValidationError(errors)

    def validate_for_publication(self) -> None:
        errors = event_publication_errors(
            {translation.language: translation for translation in self.translations.all()},
            modality=self.modality,
        )
        if not self.event_type:
            errors.append("Informe o tipo antes de publicar.")
        if not self.modality:
            errors.append("Informe a modalidade antes de publicar.")
        if self.start_date is None or self.end_date is None:
            errors.append("Informe as datas de início e término antes de publicar.")
        if not self.is_all_day and (self.start_time is None or self.end_time is None):
            errors.append("Informe os horários de início e término antes de publicar.")
        if (
            self.modality in {self.Modality.ONLINE, self.Modality.HYBRID}
            and not (self.online_url or "").strip()
        ):
            errors.append("Informe a URL de acesso para esta modalidade.")
        if errors:
            raise ValidationError(errors)

    def temporal_state(self, reference: datetime | None = None) -> str:
        if self.start_date is None or self.end_date is None:
            raise ValueError("Evento sem datas completas.")
        local_reference = timezone.localtime(reference or timezone.now())
        if self.is_all_day:
            if local_reference.date() < self.start_date:
                return self.TemporalState.UPCOMING
            if local_reference.date() > self.end_date:
                return self.TemporalState.PAST
            return self.TemporalState.ONGOING

        if self.start_time is None or self.end_time is None:
            raise ValueError("Evento com horário incompleto.")
        current_timezone = timezone.get_current_timezone()
        starts_at = timezone.make_aware(
            datetime.combine(self.start_date, self.start_time),
            current_timezone,
        )
        ends_at = timezone.make_aware(
            datetime.combine(self.end_date, self.end_time),
            current_timezone,
        )
        if local_reference < starts_at:
            return self.TemporalState.UPCOMING
        if local_reference >= ends_at:
            return self.TemporalState.PAST
        return self.TemporalState.ONGOING


class EventTranslation(models.Model):
    class Language(models.TextChoices):
        PT_BR = "pt-br", "Português (Brasil)"
        EN = "en", "English"

    event = models.ForeignKey(Event, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("idioma", max_length=5, choices=Language)
    title = models.CharField("título", max_length=200, blank=True)
    slug = models.SlugField(max_length=220, null=True, blank=True)
    summary = models.TextField("resumo", max_length=400, blank=True)
    body_html = models.TextField("descrição", blank=True)
    location_name = models.CharField("nome do local", max_length=200, blank=True)
    location_address = models.CharField("endereço", max_length=300, blank=True)
    cover_alt_text = models.CharField(
        "texto alternativo da imagem",
        max_length=250,
        blank=True,
    )
    seo_title = models.CharField("título para SEO", max_length=70, blank=True)
    seo_description = models.CharField("descrição para SEO", max_length=160, blank=True)

    class Meta:
        verbose_name = "tradução"
        verbose_name_plural = "traduções"
        ordering = ("language",)
        constraints = [
            models.UniqueConstraint(
                fields=("event", "language"),
                name="unique_event_translation_language",
            ),
            models.UniqueConstraint(
                fields=("language", "slug"),
                condition=models.Q(slug__isnull=False),
                name="unique_event_translation_slug_per_language",
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


def event_publication_errors(
    translations: dict[str, EventTranslation],
    *,
    modality: str,
) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "title": "título",
        "slug": "slug",
        "summary": "resumo",
        "body_html": "descrição",
    }
    for language, label in EventTranslation.Language.choices:
        translation = translations.get(language)
        if translation is None:
            errors.append(f"A tradução em {label} é obrigatória para publicar.")
            continue
        for field, field_label in required_fields.items():
            if not (getattr(translation, field, None) or "").strip():
                errors.append(f"Preencha {field_label} na tradução em {label}.")
        if (
            modality in {Event.Modality.IN_PERSON, Event.Modality.HYBRID}
            and not (translation.location_name or "").strip()
        ):
            errors.append(f"Preencha nome do local na tradução em {label}.")
    return errors
