import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.projects.models import Project
from apps.publications.models import (
    Publication,
    PublicationAuthor,
    PublicationTranslation,
    publication_errors,
)
from apps.publications.validators import validate_publication_cover
from apps.researchers.models import Researcher

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "publications"
MODEL_FIELDS = (
    "status",
    "year",
    "venue",
    "doi",
    "external_url",
    "display_order",
    "published_at",
    "cover_credit",
)
TRANSLATION_FIELDS = (
    "language",
    "title",
    "abstract",
    "cover_alt_text",
    "seo_title",
    "seo_description",
)
AUTHOR_FIELDS = ("researcher", "external_name", "display_order")


@dataclass
class SeedPublication:
    values: dict
    translations: list[dict]
    authors: list[dict]
    project: dict | None
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
        raise CommandError(f"Não foi possível ler o seed de publicações: {exc}") from exc
    require_fields(raw, ("publications",), "data.json")
    if not isinstance(raw["publications"], list) or not raw["publications"]:
        raise CommandError("publications deve ser uma lista não vazia.")

    payload, identities = [], set()
    for index, entry in enumerate(raw["publications"]):
        label = f"publications[{index}]"
        require_fields(entry, (*MODEL_FIELDS, "cover", "translations", "authors", "project"), label)
        if type(entry["display_order"]) is not int:
            raise CommandError(f"{label}.display_order deve ser inteiro.")
        if entry["year"] is not None and type(entry["year"]) is not int:
            raise CommandError(f"{label}.year deve ser inteiro ou nulo.")
        publication = Publication(**{field: entry[field] for field in MODEL_FIELDS})
        clean(publication, label)
        translations, languages = [], set()
        if not isinstance(entry["translations"], list):
            raise CommandError(f"{label}.translations deve ser uma lista.")
        for translation in entry["translations"]:
            require_fields(translation, TRANSLATION_FIELDS, f"{label}.translations")
            instance = PublicationTranslation(**translation)
            clean(instance, f"{label}.translations", exclude=("publication",))
            if instance.language in languages:
                raise CommandError(f"Idioma duplicado em {label}: {instance.language}.")
            languages.add(instance.language)
            translations.append({field: getattr(instance, field) for field in TRANSLATION_FIELDS})
        if publication.status == Publication.Status.PUBLISHED:
            errors = publication_errors(
                {item["language"]: PublicationTranslation(**item) for item in translations}
            )
            if errors:
                raise CommandError(f"{label}: {'; '.join(errors)}")
        identity = publication.doi or (
            publication.year,
            publication.venue,
            tuple(sorted((item["language"], item["title"]) for item in translations)),
        )
        if identity in identities:
            raise CommandError(f"Publicação duplicada em {label}.")
        identities.add(identity)
        if not isinstance(entry["authors"], list):
            raise CommandError(f"{label}.authors deve ser uma lista.")
        orders, researchers = set(), set()
        for author in entry["authors"]:
            require_fields(author, AUTHOR_FIELDS, f"{label}.authors")
            name, external, order = (author[field] for field in AUTHOR_FIELDS)
            if name is not None and (not isinstance(name, str) or not name.strip()):
                raise CommandError(f"{label}.authors.researcher deve ser um nome ou nulo.")
            if not isinstance(external, str) or bool(name) == bool(external.strip()):
                raise CommandError(f"{label}: cada autor deve ter somente uma identidade.")
            if type(order) is not int or order < 0 or order in orders:
                raise CommandError(f"{label}: ordens dos autores devem ser inteiras e diferentes.")
            if len(external) > PublicationAuthor._meta.get_field("external_name").max_length:
                raise CommandError(f"{label}: nome do autor externo muito longo.")
            if name is not None and name in researchers:
                raise CommandError(f"{label}: pesquisador duplicado entre os autores.")
            orders.add(order)
            if name is not None:
                researchers.add(name)
        if publication.status == Publication.Status.PUBLISHED and not entry["authors"]:
            raise CommandError(f"{label}: informe pelo menos um autor antes de publicar.")
        if entry["project"] is not None:
            require_fields(entry["project"], ("language", "slug"), f"{label}.project")
            if (
                entry["project"]["language"] not in PublicationTranslation.Language.values
                or not isinstance(entry["project"]["slug"], str)
                or not entry["project"]["slug"]
            ):
                raise CommandError(f"{label}.project contém idioma ou slug inválido.")
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
                    validate_publication_cover(File(source, name=filename))
            except (OSError, ValidationError) as exc:
                raise CommandError(f"Não foi possível carregar a capa {filename}: {exc}") from exc
        payload.append(
            SeedPublication(
                values={field: getattr(publication, field) for field in MODEL_FIELDS},
                translations=translations,
                authors=entry["authors"],
                project=entry["project"],
                cover=cover,
            )
        )
    return payload


def existing_publication(item):
    if item.values["doi"]:
        lookup = Q(doi__iexact=item.values["doi"])
    else:
        titles = Q(pk__in=[])
        for entry in item.translations:
            titles |= Q(
                translations__language=entry["language"], translations__title=entry["title"]
            )
        lookup = Q(year=item.values["year"], venue=item.values["venue"]) & titles
    matches = list(Publication.objects.filter(lookup).distinct()[:2])
    if len(matches) > 1:
        raise CommandError("Cadastros conflitantes para a publicação do seed.")
    return bool(matches)


def related_objects(item):
    project = None
    if item.project:
        projects = list(
            Project.objects.filter(
                translations__language=item.project["language"],
                translations__slug=item.project["slug"],
            ).distinct()[:2]
        )
        if len(projects) != 1:
            raise CommandError(f"Cadastre o projeto {item.project['slug']} antes das publicações.")
        project = projects[0]
    authors = []
    for entry in item.authors:
        researcher = None
        if entry["researcher"] is not None:
            matches = list(Researcher.objects.filter(full_name=entry["researcher"])[:2])
            if len(matches) != 1:
                raise CommandError(
                    f"Pesquisador não encontrado ou ambíguo: {entry['researcher']}. "
                    "Execute seed_researchers e confira os nomes antes de seed_publications."
                )
            researcher = matches[0]
        author = PublicationAuthor(
            researcher=researcher,
            external_name=entry["external_name"],
            display_order=entry["display_order"],
        )
        clean(author, "Autor", exclude=("publication",))
        authors.append(author)
    return project, authors


class Command(BaseCommand):
    help = "Cria as publicações do acervo inicial com autores e capas, preservando as existentes."

    def handle(self, *args, **options):
        payload = load_seed_payload()
        created_files = []
        created = preserved = 0
        try:
            with transaction.atomic():
                pending = []
                for item in payload:
                    if existing_publication(item):
                        preserved += 1
                        continue
                    project, authors = related_objects(item)
                    pending.append((item, project, authors))
                for item, project, authors in pending:
                    publication = Publication(project=project, **item.values)
                    if item.cover:
                        with item.cover.open("rb") as source:
                            publication.cover.save(item.cover.name, File(source), save=False)
                        created_files.append((publication.cover.storage, publication.cover.name))
                    publication.save()
                    PublicationTranslation.objects.bulk_create(
                        PublicationTranslation(publication=publication, **entry)
                        for entry in item.translations
                    )
                    for author in authors:
                        author.publication = publication
                        author.save()
                    if publication.status == Publication.Status.PUBLISHED:
                        publication.validate_for_publication()
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
            self.style.SUCCESS(
                f"Publicações: {created} criadas; {preserved} existentes preservadas."
            )
        )
