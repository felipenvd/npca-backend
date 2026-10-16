import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.core.images import webp_image
from apps.publications.models import Publication

from .seed_publications import MODEL_FIELDS, SEED_ROOT, TRANSLATION_FIELDS


class Command(BaseCommand):
    help = "Atualiza o seed com as publicações atuais, traduções, autores e capas em WebP."

    def handle(self, *args, **options):
        records, covers = [], {}
        try:
            with transaction.atomic():
                queryset = Publication.objects.select_related("project").prefetch_related(
                    "translations", "author_records__researcher", "project__translations"
                )
                for publication in queryset:
                    record = {field: getattr(publication, field) for field in MODEL_FIELDS}
                    record["published_at"] = (
                        publication.published_at.isoformat() if publication.published_at else None
                    )
                    translations = list(publication.translations.all())
                    record["translations"] = [
                        {field: getattr(entry, field) for field in TRANSLATION_FIELDS}
                        for entry in translations
                    ]
                    record["authors"] = [
                        {
                            "researcher": author.researcher.full_name
                            if author.researcher
                            else None,
                            "external_name": author.external_name,
                            "display_order": author.display_order,
                        }
                        for author in publication.author_records.all()
                    ]
                    record["project"] = None
                    if publication.project:
                        reference = next(
                            (
                                entry
                                for entry in publication.project.translations.all()
                                if entry.slug
                            ),
                            None,
                        )
                        if reference is None:
                            raise CommandError(f"O projeto {publication.project_id} não tem slug.")
                        record["project"] = {"language": reference.language, "slug": reference.slug}
                    record["cover"] = None
                    if publication.cover:
                        title = next(
                            (entry.title for entry in translations if entry.language == "pt-br"), ""
                        )
                        filename = f"{slugify(title)[:100] or 'publicacao'}-{publication.pk}.webp"
                        if filename in covers:
                            raise CommandError(f"Nome de capa duplicado: {filename}.")
                        with publication.cover.open("rb") as source:
                            covers[filename] = webp_image(source.read())
                        record["cover"] = filename
                    records.append(record)
            if not records:
                raise CommandError(
                    "Nenhuma publicação encontrada; o seed existente foi preservado."
                )
            directory = SEED_ROOT / "covers"
            directory.mkdir(parents=True, exist_ok=True)
            for filename, content in covers.items():
                (directory / filename).write_bytes(content)
            manifest = SEED_ROOT / "data.json"
            temporary = manifest.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"publications": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(manifest)
        except OSError as exc:
            raise CommandError(f"Não foi possível exportar as publicações: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed atualizado: {len(records)} publicações e {len(covers)} capas WebP."
            )
        )
