from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import Course, CourseTranslation, course_publication_errors

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "courses"
MANIFEST_PATH = SEED_ROOT / "data.json"

ROOT_FIELDS = {"courses"}
COURSE_FIELDS = {"course_type", "external_url", "is_featured", "translations"}
TRANSLATION_FIELDS = {"language", "title", "summary", "cover_alt_text"}


@dataclass(frozen=True)
class SeedCourse:
    values: dict[str, Any]
    translations: list[dict[str, str]]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommandError(f"{label} deve ser um objeto JSON.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CommandError(f"{label} deve ser uma lista JSON.")
    return value


def _require_exact_fields(values: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(fields - values.keys())
    unexpected = sorted(values.keys() - fields)
    if missing:
        raise CommandError(f"{label} não contém: {', '.join(missing)}.")
    if unexpected:
        raise CommandError(f"{label} contém campos desconhecidos: {', '.join(unexpected)}.")


def _validation_error(label: str, error: ValidationError) -> CommandError:
    return CommandError(f"{label}: {'; '.join(error.messages)}")


def _normalize_translations(raw: Any, label: str) -> list[dict[str, str]]:
    translations: list[dict[str, str]] = []
    seen_languages: set[str] = set()
    for index, raw_translation in enumerate(_require_list(raw, f"{label}.translations")):
        translation_label = f"{label}.translations[{index}]"
        values = _require_mapping(raw_translation, translation_label)
        _require_exact_fields(values, TRANSLATION_FIELDS, translation_label)
        instance = CourseTranslation(**values)
        try:
            instance.full_clean(exclude={"course"}, validate_constraints=False)
        except ValidationError as error:
            raise _validation_error(translation_label, error) from error
        if instance.language in seen_languages:
            raise CommandError(f"{label} contém o idioma {instance.language} duplicado.")
        seen_languages.add(instance.language)
        translations.append({field: getattr(instance, field) for field in TRANSLATION_FIELDS})

    required_languages = {choice[0] for choice in CourseTranslation.Language.choices}
    if seen_languages != required_languages:
        missing = sorted(required_languages - seen_languages)
        raise CommandError(f"{label} não contém as traduções: {', '.join(missing)}.")
    publication_errors = course_publication_errors(
        {translation["language"]: CourseTranslation(**translation) for translation in translations}
    )
    if publication_errors:
        raise CommandError(f"{label}: {'; '.join(publication_errors)}")
    return translations


def load_seed_payload() -> list[SeedCourse]:
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CommandError(f"Manifesto de seed não encontrado: {MANIFEST_PATH}.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(f"Não foi possível ler o manifesto {MANIFEST_PATH}: {error}.") from error

    root = _require_mapping(raw, "data.json")
    _require_exact_fields(root, ROOT_FIELDS, "data.json")
    payload: list[SeedCourse] = []
    seen_urls: set[str] = set()
    for order, raw_course in enumerate(_require_list(root["courses"], "courses")):
        label = f"courses[{order}]"
        values = _require_mapping(raw_course, label)
        _require_exact_fields(values, COURSE_FIELDS, label)
        if not isinstance(values["is_featured"], bool):
            raise CommandError(f"{label}.is_featured deve ser booleano.")
        translations = _normalize_translations(values["translations"], label)
        instance = Course(
            status=Course.Status.DRAFT,
            course_type=values["course_type"],
            external_url=values["external_url"],
            is_featured=values["is_featured"],
            display_order=order,
        )
        try:
            instance.full_clean(validate_constraints=False)
        except ValidationError as error:
            raise _validation_error(label, error) from error
        if instance.external_url in seen_urls:
            raise CommandError(f"courses contém a URL duplicada {instance.external_url}.")
        seen_urls.add(instance.external_url)
        payload.append(
            SeedCourse(
                values={
                    "status": instance.status,
                    "course_type": instance.course_type,
                    "external_url": instance.external_url,
                    "is_featured": instance.is_featured,
                    "display_order": instance.display_order,
                },
                translations=translations,
            )
        )
    return payload


class Command(BaseCommand):
    help = "Cria os cursos e tutoriais externos iniciais como rascunhos."

    def handle(self, *args, **options) -> None:
        payload = load_seed_payload()
        if Course.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Cursos ou tutoriais já existem; nenhuma alteração foi realizada."
                )
            )
            return

        with transaction.atomic():
            for item in payload:
                course = Course.objects.create(**item.values)
                CourseTranslation.objects.bulk_create(
                    CourseTranslation(course=course, **translation)
                    for translation in item.translations
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga inicial criada: {len(payload)} cursos e tutoriais em rascunho."
            )
        )
