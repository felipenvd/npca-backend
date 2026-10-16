import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.projects.models import (
    Project,
    ProjectTeamMember,
    ProjectTranslation,
    publication_errors,
)
from apps.projects.validators import validate_project_cover
from apps.researchers.models import Researcher

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "projects"
MODEL_FIELDS = (
    "status",
    "situation",
    "start_year",
    "end_year",
    "is_featured",
    "display_order",
    "published_at",
    "cover_credit",
    "funding",
    "partners",
    "website_url",
    "repository_url",
)
TRANSLATION_FIELDS = (
    "language",
    "title",
    "slug",
    "summary",
    "body_html",
    "seo_title",
    "seo_description",
)


@dataclass
class SeedProject:
    values: dict
    translations: list[dict]
    coordinator: str | None
    team: list[dict]
    cover: Path | None


def require_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise CommandError(f"{label} contém campos inválidos. Esperado: {', '.join(fields)}.")


def clean(instance, label, *, exclude=()):
    try:
        instance.full_clean(exclude=exclude, validate_unique=False, validate_constraints=False)
    except ValidationError as exc:
        raise CommandError(f"{label}: {'; '.join(exc.messages)}") from exc


def validate_reference(name, label):
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise CommandError(f"{label} deve ser um nome ou nulo.")


def load_seed_payload():
    try:
        raw = json.loads((SEED_ROOT / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"Não foi possível ler o seed de projetos: {exc}") from exc
    require_fields(raw, ("projects",), "data.json")
    if not isinstance(raw["projects"], list) or not raw["projects"]:
        raise CommandError("projects deve ser uma lista não vazia.")

    payload, slugs = [], set()
    for index, entry in enumerate(raw["projects"]):
        label = f"projects[{index}]"
        require_fields(
            entry, (*MODEL_FIELDS, "cover", "translations", "coordinator", "team"), label
        )
        for field in ("start_year", "end_year", "display_order"):
            if type(entry[field]) is not int and not (
                field != "display_order" and entry[field] is None
            ):
                raise CommandError(f"{label}.{field} deve ser inteiro.")
        if type(entry["is_featured"]) is not bool:
            raise CommandError(f"{label}.is_featured deve ser booleano.")
        project = Project(**{field: entry[field] for field in MODEL_FIELDS})
        # Valida os metadados antes de resolver referências, sem exigir FK de publicação.
        status = project.status
        project.status = Project.Status.DRAFT
        clean(project, label)
        project.status = status
        if status not in Project.Status.values:
            raise CommandError(f"{label}.status contém uma opção inválida.")
        validate_reference(entry["coordinator"], f"{label}.coordinator")
        translations, languages = [], set()
        if not isinstance(entry["translations"], list):
            raise CommandError(f"{label}.translations deve ser uma lista.")
        for translation in entry["translations"]:
            require_fields(translation, TRANSLATION_FIELDS, f"{label}.translations")
            instance = ProjectTranslation(**translation)
            clean(instance, f"{label}.translations", exclude=("project",))
            if instance.language in languages:
                raise CommandError(f"Idioma duplicado em {label}: {instance.language}.")
            languages.add(instance.language)
            if instance.slug:
                identity = (instance.language, instance.slug)
                if identity in slugs:
                    raise CommandError(f"Slug duplicado em {label}: {instance.slug}.")
                slugs.add(identity)
            translations.append({field: getattr(instance, field) for field in TRANSLATION_FIELDS})
        if status == Project.Status.PUBLISHED:
            errors = publication_errors(
                {item["language"]: ProjectTranslation(**item) for item in translations}
            )
            if errors:
                raise CommandError(f"{label}: {'; '.join(errors)}")
        if not isinstance(entry["team"], list):
            raise CommandError(f"{label}.team deve ser uma lista.")
        researchers = set()
        for member in entry["team"]:
            require_fields(member, ("researcher", "external_name"), f"{label}.team")
            name, external = member["researcher"], member["external_name"]
            validate_reference(name, f"{label}.team.researcher")
            if not isinstance(external, str) or bool(name) == bool(external.strip()):
                raise CommandError(f"{label}: cada integrante deve ter somente uma identidade.")
            if len(external) > ProjectTeamMember._meta.get_field("external_name").max_length:
                raise CommandError(f"{label}: nome do integrante externo muito longo.")
            if name:
                if name in researchers or name == entry["coordinator"]:
                    raise CommandError(f"{label}: pesquisador duplicado na coordenação ou equipe.")
                researchers.add(name)
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
                    validate_project_cover(File(source, name=filename))
            except (OSError, ValidationError) as exc:
                raise CommandError(f"Não foi possível carregar a capa {filename}: {exc}") from exc
        payload.append(
            SeedProject(
                values={field: getattr(project, field) for field in MODEL_FIELDS},
                translations=translations,
                coordinator=entry["coordinator"],
                team=entry["team"],
                cover=cover,
            )
        )
    return payload


def existing_project(item):
    lookup = Q(pk__in=[])
    for entry in item.translations:
        identity = Q(translations__title=entry["title"]) if entry["title"] else Q(pk__in=[])
        if entry["slug"]:
            identity |= Q(translations__slug=entry["slug"])
        lookup |= Q(translations__language=entry["language"]) & identity
    matches = list(Project.objects.filter(lookup).distinct()[:2])
    if len(matches) > 1:
        raise CommandError("Cadastros conflitantes para o projeto do seed.")
    return matches[0] if matches else None


def researcher_reference(name):
    if name is None:
        return None
    matches = list(Researcher.objects.filter(full_name=name)[:2])
    if len(matches) != 1:
        raise CommandError(
            f"Pesquisador não encontrado ou ambíguo: {name}. "
            "Execute seed_researchers e confira os nomes antes de seed_projects."
        )
    return matches[0]


class Command(BaseCommand):
    help = (
        "Cria os projetos iniciais com traduções, equipes e destaques, preservando os existentes."
    )

    def handle(self, *args, **options):
        payload = load_seed_payload()
        created_files = []
        created = preserved = 0
        try:
            with transaction.atomic():
                pending, existing_ids = [], set()
                for item in payload:
                    existing = existing_project(item)
                    if existing:
                        if existing.pk in existing_ids:
                            raise CommandError(
                                "Dois projetos do seed apontam para o mesmo cadastro."
                            )
                        existing_ids.add(existing.pk)
                        preserved += 1
                        continue
                    project = Project(
                        coordinator=researcher_reference(item.coordinator), **item.values
                    )
                    clean(project, "Projeto")
                    team = []
                    for entry in item.team:
                        member = ProjectTeamMember(
                            researcher=researcher_reference(entry["researcher"]),
                            external_name=entry["external_name"],
                        )
                        clean(member, "Integrante", exclude=("project",))
                        team.append(member)
                    pending.append((item, project, team))
                for item, project, team in pending:
                    if item.cover:
                        with item.cover.open("rb") as source:
                            project.cover.save(item.cover.name, File(source), save=False)
                        created_files.append((project.cover.storage, project.cover.name))
                    project.save()
                    ProjectTranslation.objects.bulk_create(
                        ProjectTranslation(project=project, **entry) for entry in item.translations
                    )
                    for member in team:
                        member.project = project
                        member.save()
                    if project.status == Project.Status.PUBLISHED:
                        project.validate_for_publication()
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
            self.style.SUCCESS(f"Projetos: {created} criados; {preserved} existentes preservados.")
        )
