import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.core.images import webp_image
from apps.projects.models import Project

from .seed_projects import MODEL_FIELDS, SEED_ROOT, TRANSLATION_FIELDS


class Command(BaseCommand):
    help = "Atualiza o seed com os projetos atuais, traduções, equipes e capas em WebP."

    def handle(self, *args, **options):
        records, covers = [], {}
        try:
            with transaction.atomic():
                queryset = Project.objects.select_related("coordinator").prefetch_related(
                    "translations", "team_memberships__researcher"
                )
                for project in queryset:
                    record = {field: getattr(project, field) for field in MODEL_FIELDS}
                    record["published_at"] = (
                        project.published_at.isoformat() if project.published_at else None
                    )
                    translations = list(project.translations.all())
                    record["translations"] = [
                        {field: getattr(entry, field) for field in TRANSLATION_FIELDS}
                        for entry in translations
                    ]
                    record["coordinator"] = (
                        project.coordinator.full_name if project.coordinator else None
                    )
                    record["team"] = [
                        {
                            "researcher": member.researcher.full_name
                            if member.researcher
                            else None,
                            "external_name": member.external_name,
                        }
                        for member in project.team_memberships.all()
                    ]
                    record["cover"] = None
                    if project.cover:
                        title = next(
                            (entry.title for entry in translations if entry.language == "pt-br"), ""
                        )
                        filename = f"{slugify(title)[:100] or 'projeto'}-{project.pk}.webp"
                        with project.cover.open("rb") as source:
                            covers[filename] = webp_image(source.read())
                        record["cover"] = filename
                    records.append(record)
            if not records:
                raise CommandError("Nenhum projeto encontrado; o seed existente foi preservado.")
            SEED_ROOT.mkdir(parents=True, exist_ok=True)
            if covers:
                directory = SEED_ROOT / "covers"
                directory.mkdir(parents=True, exist_ok=True)
                for filename, content in covers.items():
                    (directory / filename).write_bytes(content)
            manifest = SEED_ROOT / "data.json"
            temporary = manifest.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"projects": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(manifest)
        except OSError as exc:
            raise CommandError(f"Não foi possível exportar os projetos: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed atualizado: {len(records)} projetos e {len(covers)} capas WebP."
            )
        )
