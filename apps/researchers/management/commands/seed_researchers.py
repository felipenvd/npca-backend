import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.researchers.models import Researcher, ResearcherTranslation, activation_errors
from apps.researchers.validators import validate_researcher_photo

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "researchers"
RESEARCHER_FIELDS = (
    "full_name",
    "academic_category",
    "is_active",
    "display_order",
    "public_email",
    "lattes_url",
    "orcid_url",
    "linkedin_url",
    "photo_crop",
)
TRANSLATION_FIELDS = (
    "language",
    "slug",
    "research_area",
    "biography_html",
    "seo_title",
    "seo_description",
)
PHOTO_FIELDS = ("photo", "photo_cropped")


@dataclass
class SeedResearcher:
    values: dict
    translations: list[dict]
    photos: dict[str, Path]


def require_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CommandError(f"{label} contém campos inválidos. Esperado: {', '.join(fields)}.")


def load_seed_payload(root=None):
    root = root or SEED_ROOT
    try:
        raw = json.loads((root / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"Não foi possível ler o seed de pesquisadores: {exc}") from exc
    require_fields(raw, ("researchers",), "data.json")
    if not isinstance(raw["researchers"], list) or not raw["researchers"]:
        raise CommandError("researchers deve ser uma lista não vazia.")

    payload = []
    seen_names, seen_slugs = set(), set()
    for index, item in enumerate(raw["researchers"]):
        label = f"researchers[{index}]"
        require_fields(item, (*RESEARCHER_FIELDS, *PHOTO_FIELDS, "translations"), label)
        if not isinstance(item["is_active"], bool):
            raise CommandError(f"{label}.is_active deve ser booleano.")
        if type(item["display_order"]) is not int:
            raise CommandError(f"{label}.display_order deve ser inteiro.")
        values = {name: item[name] for name in RESEARCHER_FIELDS}
        researcher = Researcher(**values)
        try:
            researcher.full_clean(validate_constraints=False)
        except ValidationError as exc:
            raise CommandError(f"{label}: {'; '.join(exc.messages)}") from exc
        if researcher.full_name in seen_names:
            raise CommandError(f"Nome duplicado no seed: {researcher.full_name}.")
        seen_names.add(researcher.full_name)

        translations = []
        languages = set()
        if not isinstance(item["translations"], list):
            raise CommandError(f"{label}.translations deve ser uma lista.")
        for entry in item["translations"]:
            require_fields(entry, TRANSLATION_FIELDS, f"{label}.translations")
            translation = ResearcherTranslation(researcher=researcher, **entry)
            try:
                translation.full_clean(exclude={"researcher"}, validate_constraints=False)
            except ValidationError as exc:
                raise CommandError(f"{label}: {'; '.join(exc.messages)}") from exc
            slug_key = (translation.language, translation.slug)
            if translation.language in languages or slug_key in seen_slugs:
                raise CommandError(f"Idioma ou slug duplicado no seed: {slug_key}.")
            languages.add(translation.language)
            seen_slugs.add(slug_key)
            translations.append({name: getattr(translation, name) for name in TRANSLATION_FIELDS})
        if languages != set(ResearcherTranslation.Language.values):
            raise CommandError(f"{label} deve conter português e inglês.")
        if researcher.is_active:
            errors = activation_errors(
                {entry["language"]: ResearcherTranslation(**entry) for entry in translations},
                researcher.academic_category,
            )
            if errors:
                raise CommandError(f"{label}: {'; '.join(errors)}")

        photos = {}
        for name in PHOTO_FIELDS:
            filename = item[name]
            if filename is None:
                continue
            if not isinstance(filename, str) or not filename or Path(filename).name != filename:
                raise CommandError(f"{label}.{name} deve conter somente o nome do arquivo.")
            path = (root / "photos" / filename).resolve()
            if not path.is_relative_to((root / "photos").resolve()):
                raise CommandError(f"Foto fora da pasta de seed: {filename}.")
            try:
                with path.open("rb") as source:
                    validate_researcher_photo(File(source, name=filename))
            except (OSError, ValidationError) as exc:
                raise CommandError(f"Não foi possível carregar a foto {filename}: {exc}") from exc
            photos[name] = path
        if "photo_cropped" in photos and "photo" not in photos:
            raise CommandError(f"{label} contém recorte sem a foto original.")
        payload.append(SeedResearcher(values=values, translations=translations, photos=photos))
    return payload


class Command(BaseCommand):
    help = "Cria os pesquisadores do acervo inicial, preservando os cadastros existentes."

    def handle(self, *args, **options):
        payload = load_seed_payload()
        created_files = []
        created = preserved = 0
        try:
            with transaction.atomic():
                for item in payload:
                    lookup = Q(full_name=item.values["full_name"])
                    for entry in item.translations:
                        lookup |= Q(
                            translations__language=entry["language"],
                            translations__slug=entry["slug"],
                        )
                    matches = list(Researcher.objects.filter(lookup).distinct()[:2])
                    if len(matches) > 1:
                        raise CommandError(
                            f"Cadastros conflitantes para {item.values['full_name']}."
                        )
                    if matches:
                        preserved += 1
                        continue

                    researcher = Researcher(**item.values)
                    for name, path in item.photos.items():
                        field = getattr(researcher, name)
                        with path.open("rb") as source:
                            field.save(path.name, File(source), save=False)
                        created_files.append((field.storage, field.name))
                    researcher.save()
                    for entry in item.translations:
                        ResearcherTranslation.objects.create(researcher=researcher, **entry)
                    if researcher.is_active:
                        researcher.validate_for_activation()
                    created += 1
        except Exception as exc:
            for storage, name in created_files:
                try:
                    storage.delete(name)
                except OSError as cleanup_error:
                    self.stderr.write(f"Não foi possível remover a mídia {name}: {cleanup_error}.")
            if isinstance(exc, OSError):
                raise CommandError(
                    f"Não foi possível gravar as fotos em MEDIA_ROOT: {exc}"
                ) from exc
            raise
        self.stdout.write(
            self.style.SUCCESS(
                f"Pesquisadores: {created} criados; {preserved} existentes preservados."
            )
        )
