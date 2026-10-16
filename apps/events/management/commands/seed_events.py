import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from apps.events.models import Event, EventTranslation, event_publication_errors
from apps.events.validators import validate_event_cover

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "events"
MODEL_FIELDS = (
    "status",
    "schedule_status",
    "event_type",
    "modality",
    "start_date",
    "end_date",
    "is_all_day",
    "start_time",
    "end_time",
    "online_url",
    "registration_url",
    "display_order",
    "published_at",
    "cover_credit",
    "cover_position_x",
    "cover_position_y",
    "cover_zoom",
)
TRANSLATION_FIELDS = (
    "language",
    "title",
    "slug",
    "summary",
    "body_html",
    "location_name",
    "location_address",
    "cover_alt_text",
    "seo_title",
    "seo_description",
)
TEMPORAL_FIELDS = {
    "start_date": parse_date,
    "end_date": parse_date,
    "start_time": parse_time,
    "end_time": parse_time,
    "published_at": parse_datetime,
}


@dataclass
class SeedEvent:
    values: dict
    translations: list[dict]
    cover: Path | None


def require_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CommandError(f"{label} contém campos inválidos. Esperado: {', '.join(fields)}.")


def clean(instance, label, *, exclude=()):
    try:
        instance.full_clean(exclude=exclude, validate_unique=False, validate_constraints=False)
    except ValidationError as exc:
        raise CommandError(f"{label}: {'; '.join(exc.messages)}") from exc


def load_seed_payload():
    try:
        raw = json.loads((SEED_ROOT / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"Não foi possível ler o seed de eventos: {exc}") from exc
    require_fields(raw, ("events",), "data.json")
    if not isinstance(raw["events"], list) or not raw["events"]:
        raise CommandError("events deve ser uma lista não vazia.")

    payload, identities = [], set()
    for index, entry in enumerate(raw["events"]):
        label = f"events[{index}]"
        require_fields(entry, (*MODEL_FIELDS, "cover", "translations"), label)
        values = {field: entry[field] for field in MODEL_FIELDS}
        for field in ("display_order", "cover_position_x", "cover_position_y", "cover_zoom"):
            if type(values[field]) is not int:
                raise CommandError(f"{label}.{field} deve ser inteiro.")
        if type(values["is_all_day"]) is not bool:
            raise CommandError(f"{label}.is_all_day deve ser booleano.")
        for field, parser in TEMPORAL_FIELDS.items():
            value = values[field]
            if value is None:
                continue
            try:
                parsed = parser(value) if isinstance(value, str) else None
            except ValueError:
                parsed = None
            if parsed is None:
                raise CommandError(f"{label}.{field} deve estar no formato ISO ou ser nulo.")
            if field == "published_at" and timezone.is_naive(parsed):
                raise CommandError(f"{label}.published_at deve incluir o fuso horário.")
            if field in ("start_time", "end_time") and parsed.tzinfo is not None:
                raise CommandError(f"{label}.{field} deve ser um horário local sem fuso.")
            values[field] = parsed
        event = Event(**values)
        clean(event, label)
        if not isinstance(entry["translations"], list):
            raise CommandError(f"{label}.translations deve ser uma lista.")
        translations, languages = [], set()
        for translation in entry["translations"]:
            require_fields(translation, TRANSLATION_FIELDS, f"{label}.translations")
            instance = EventTranslation(**translation)
            clean(instance, f"{label}.translations", exclude=("event",))
            if instance.language in languages:
                raise CommandError(f"Idioma duplicado em {label}: {instance.language}.")
            languages.add(instance.language)
            for field in ("slug", "title"):
                if value := getattr(instance, field):
                    identity = (instance.language, field, value)
                    if identity in identities:
                        raise CommandError(f"Evento duplicado em {label}: {field} {value}.")
                    identities.add(identity)
            translations.append({field: getattr(instance, field) for field in TRANSLATION_FIELDS})
        if not any(item["title"] or item["slug"] for item in translations):
            raise CommandError(
                f"{label}: informe pelo menos um título ou slug para identificar o evento."
            )
        if event.status == Event.Status.PUBLISHED:
            errors = event_publication_errors(
                {item["language"]: EventTranslation(**item) for item in translations},
                modality=event.modality,
            )
            if errors:
                raise CommandError(f"{label}: {'; '.join(errors)}")
        cover = None
        filename = entry["cover"]
        if filename is not None:
            if not isinstance(filename, str) or not filename or Path(filename).name != filename:
                raise CommandError(f"{label}.cover deve conter somente o nome do arquivo.")
            directory = (SEED_ROOT / "covers").resolve()
            cover = (directory / filename).resolve()
            if not cover.is_relative_to(directory):
                raise CommandError(f"{label}.cover está fora da pasta de seed.")
            try:
                with cover.open("rb") as source:
                    validate_event_cover(File(source, name=filename))
            except (OSError, ValidationError) as exc:
                raise CommandError(f"Não foi possível carregar a capa {filename}: {exc}") from exc
        payload.append(
            SeedEvent(
                values={field: getattr(event, field) for field in MODEL_FIELDS},
                translations=translations,
                cover=cover,
            )
        )
    return payload


def existing_event(item):
    lookup = Q(pk__in=[])
    for translation in item.translations:
        identity = Q(pk__in=[])
        if translation["title"]:
            identity |= Q(translations__title=translation["title"])
        if translation["slug"]:
            identity |= Q(translations__slug=translation["slug"])
        lookup |= Q(translations__language=translation["language"]) & identity
    matches = list(Event.objects.filter(lookup).distinct()[:2])
    if len(matches) > 1:
        raise CommandError("Cadastros conflitantes para o evento do seed.")
    return matches[0] if matches else None


class Command(BaseCommand):
    help = (
        "Cria os eventos iniciais com traduções, capas e enquadramento, preservando os existentes."
    )

    def handle(self, *args, **options):
        payload = load_seed_payload()
        created_files = []
        created = preserved = 0
        try:
            with transaction.atomic():
                pending, existing_ids = [], set()
                for item in payload:
                    existing = existing_event(item)
                    if existing:
                        if existing.pk in existing_ids:
                            raise CommandError(
                                "Dois eventos do seed apontam para o mesmo cadastro."
                            )
                        existing_ids.add(existing.pk)
                        preserved += 1
                    else:
                        pending.append(item)
                for item in pending:
                    event = Event(**item.values)
                    if item.cover:
                        with item.cover.open("rb") as source:
                            event.cover.save(item.cover.name, File(source), save=False)
                        created_files.append((event.cover.storage, event.cover.name))
                    event.save()
                    EventTranslation.objects.bulk_create(
                        EventTranslation(event=event, **entry) for entry in item.translations
                    )
                    if event.status == Event.Status.PUBLISHED:
                        event.validate_for_publication()
                    created += 1
        except Exception as exc:
            for storage, name in created_files:
                try:
                    storage.delete(name)
                except OSError as cleanup_error:
                    self.stderr.write(f"Não foi possível remover a capa {name}: {cleanup_error}.")
            if isinstance(exc, OSError):
                raise CommandError(
                    f"Não foi possível gravar as capas em MEDIA_ROOT: {exc}"
                ) from exc
            raise
        self.stdout.write(
            self.style.SUCCESS(f"Eventos: {created} criados; {preserved} existentes preservados.")
        )
