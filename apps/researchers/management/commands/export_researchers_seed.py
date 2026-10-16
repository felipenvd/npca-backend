import json
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, ImageCms, ImageOps

from apps.researchers.models import Researcher

from .seed_researchers import PHOTO_FIELDS, RESEARCHER_FIELDS, SEED_ROOT, TRANSLATION_FIELDS


def webp_image(content):
    with Image.open(BytesIO(content)) as original:
        if original.format == "WEBP":
            return content
        image = ImageOps.exif_transpose(original)
        mode = "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
        profile = original.info.get("icc_profile")
        if profile:
            try:
                image = ImageCms.profileToProfile(
                    image,
                    ImageCms.ImageCmsProfile(BytesIO(profile)),
                    ImageCms.createProfile("sRGB"),
                    outputMode=mode,
                )
            except ImageCms.PyCMSError:
                image = image.convert(mode)
        else:
            image = image.convert(mode)
        output = BytesIO()
        image.save(output, "WEBP", quality=90, method=6)
        return output.getvalue()


def previous_photo_names(root):
    try:
        previous = json.loads((root / "data.json").read_text(encoding="utf-8"))
        return {
            entry[name]
            for entry in previous["researchers"]
            for name in PHOTO_FIELDS
            if isinstance(entry.get(name), str) and Path(entry[name]).name == entry[name]
        }
    except OSError, ValueError, KeyError, TypeError, AttributeError:
        return set()


class Command(BaseCommand):
    help = "Atualiza o seed com os pesquisadores e fotos em WebP do banco atual."

    def handle(self, *args, **options):
        records, photos, filenames = [], {}, set()
        try:
            with transaction.atomic():
                for researcher in Researcher.objects.prefetch_related("translations"):
                    record = {name: getattr(researcher, name) for name in RESEARCHER_FIELDS}
                    record["translations"] = [
                        {name: getattr(entry, name) for name in TRANSLATION_FIELDS}
                        for entry in researcher.translations.all()
                    ]
                    for name in PHOTO_FIELDS:
                        field = getattr(researcher, name)
                        record[name] = None
                        if not field:
                            continue
                        suffix = "-cropped" if name == "photo_cropped" else ""
                        filename = f"{slugify(researcher.full_name)}{suffix}.webp"
                        if filename in filenames:
                            raise CommandError(f"Nome de foto duplicado: {filename}.")
                        filenames.add(filename)
                        with field.open("rb") as source:
                            photos[filename] = webp_image(source.read())
                        record[name] = filename
                    records.append(record)
            if not records:
                raise CommandError(
                    "Nenhum pesquisador encontrado; o seed existente foi preservado."
                )
            # Read every source before updating the versioned seed assets.
            old_photos = previous_photo_names(SEED_ROOT)
            photo_root = SEED_ROOT / "photos"
            photo_root.mkdir(parents=True, exist_ok=True)
            for filename, content in photos.items():
                (photo_root / filename).write_bytes(content)
            manifest = SEED_ROOT / "data.json"
            temporary = manifest.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"researchers": records}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(manifest)
            # Remove only replaced JPEG/PNG files referenced by the previous manifest.
            for filename in old_photos - photos.keys():
                if Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    (photo_root / filename).unlink(missing_ok=True)
        except OSError as exc:
            raise CommandError(f"Não foi possível exportar os pesquisadores: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed atualizado: {len(records)} pesquisadores e {len(photos)} arquivos de foto."
            )
        )
