import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.core.images import webp_image
from apps.events.models import Event

from .seed_events import MODEL_FIELDS, SEED_ROOT, TEMPORAL_FIELDS, TRANSLATION_FIELDS


class Command(BaseCommand):
    help = "Atualiza o seed com os eventos atuais, traduções, capas WebP, posição e zoom."

    def handle(self, *args, **options):
        records, covers = [], {}
        try:
            with transaction.atomic():
                for event in Event.objects.prefetch_related("translations"):
                    record = {field: getattr(event, field) for field in MODEL_FIELDS}
                    for field in TEMPORAL_FIELDS:
                        value = record[field]
                        record[field] = value.isoformat() if value is not None else None
                    translations = list(event.translations.all())
                    record["translations"] = [
                        {field: getattr(entry, field) for field in TRANSLATION_FIELDS}
                        for entry in translations
                    ]
                    record["cover"] = None
                    if event.cover:
                        title = next(
                            (entry.title for entry in translations if entry.language == "pt-br"), ""
                        )
                        filename = f"{slugify(title)[:100] or 'evento'}-{event.pk}.webp"
                        with event.cover.open("rb") as source:
                            covers[filename] = webp_image(source.read())
                        record["cover"] = filename
                    records.append(record)
            if not records:
                raise CommandError("Nenhum evento encontrado; o seed existente foi preservado.")
            SEED_ROOT.mkdir(parents=True, exist_ok=True)
            if covers:
                directory = SEED_ROOT / "covers"
                directory.mkdir(parents=True, exist_ok=True)
                for filename, content in covers.items():
                    (directory / filename).write_bytes(content)
            manifest = SEED_ROOT / "data.json"
            temporary = manifest.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"events": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(manifest)
        except OSError as exc:
            raise CommandError(f"Não foi possível exportar os eventos: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed atualizado: {len(records)} eventos e {len(covers)} capas WebP."
            )
        )
