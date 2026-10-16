import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.core.images import webp_image
from apps.courses.models import Course

from .seed_courses import MODEL_FIELDS, SEED_ROOT, TRANSLATION_FIELDS


class Command(BaseCommand):
    help = "Atualiza o seed com os cursos atuais, traduções, status e capas em WebP."

    def handle(self, *args, **options):
        records, covers = [], {}
        try:
            with transaction.atomic():
                for course in Course.objects.prefetch_related("translations"):
                    record = {field: getattr(course, field) for field in MODEL_FIELDS}
                    record["published_at"] = (
                        course.published_at.isoformat() if course.published_at else None
                    )
                    translations = list(course.translations.all())
                    record["translations"] = [
                        {field: getattr(entry, field) for field in sorted(TRANSLATION_FIELDS)}
                        for entry in translations
                    ]
                    record["cover"] = None
                    if course.cover:
                        title = next(
                            (entry.title for entry in translations if entry.language == "pt-br"), ""
                        )
                        filename = f"{slugify(title)[:100] or f'curso-{course.pk}'}.webp"
                        if filename in covers:
                            raise CommandError(f"Nome de capa duplicado: {filename}.")
                        with course.cover.open("rb") as source:
                            covers[filename] = webp_image(source.read())
                        record["cover"] = filename
                    records.append(record)
            if not records:
                raise CommandError("Nenhum curso encontrado; o seed existente foi preservado.")
            directory = SEED_ROOT / "covers"
            directory.mkdir(parents=True, exist_ok=True)
            for filename, content in covers.items():
                (directory / filename).write_bytes(content)
            manifest = SEED_ROOT / "data.json"
            temporary = manifest.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"courses": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(manifest)
        except OSError as exc:
            raise CommandError(f"Não foi possível exportar os cursos: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed atualizado: {len(records)} cursos e tutoriais e {len(covers)} capas WebP."
            )
        )
