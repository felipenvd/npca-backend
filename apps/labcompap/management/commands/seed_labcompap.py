from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Model

from ...models import LabEquipment, LabGalleryImage
from ...validators import validate_labcompap_image

SEED_ROOT = settings.BASE_DIR / "scripts" / "seed" / "labcompap"
MANIFEST_PATH = SEED_ROOT / "data.json"

EQUIPMENT_FIELDS = {"inventory_code", "name_pt_br", "name_en", "brand", "model_name"}
GALLERY_IMAGE_FIELDS = {
    "file",
    "credit",
    "alt_text_pt_br",
    "alt_text_en",
    "caption_pt_br",
    "caption_en",
}
ROOT_FIELDS = {"equipment", "gallery_images"}


@dataclass(frozen=True)
class SeedImage:
    path: Path
    values: dict[str, Any]


@dataclass(frozen=True)
class SeedPayload:
    equipment: list[dict[str, Any]]
    gallery_images: list[SeedImage]


def _command_error(label: str, error: ValidationError) -> CommandError:
    return CommandError(f"{label}: {'; '.join(error.messages)}")


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


def _validate_model(instance: Model, label: str, *, exclude: set[str] | None = None) -> None:
    try:
        instance.full_clean(
            exclude=exclude,
            validate_unique=False,
            validate_constraints=False,
        )
    except ValidationError as error:
        raise _command_error(label, error) from error


def _model_values(instance: Model, fields: set[str]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


def _normalize_equipment(raw: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for order, raw_item in enumerate(_require_list(raw, "equipment")):
        label = f"equipment[{order}]"
        values = _require_mapping(raw_item, label)
        _require_exact_fields(values, EQUIPMENT_FIELDS, label)
        instance = LabEquipment(display_order=order, **values)
        _validate_model(instance, label)
        normalized.append({**_model_values(instance, EQUIPMENT_FIELDS), "display_order": order})

    inventory_codes = [item["inventory_code"] for item in normalized]
    if len(inventory_codes) != len(set(inventory_codes)):
        raise CommandError("equipment contém códigos de inventário duplicados.")
    return normalized


def _normalize_images(raw: Any) -> list[SeedImage]:
    normalized: list[SeedImage] = []
    seen_files: set[str] = set()
    metadata_fields = GALLERY_IMAGE_FIELDS - {"file"}

    for order, raw_item in enumerate(_require_list(raw, "gallery_images")):
        label = f"gallery_images[{order}]"
        values = _require_mapping(raw_item, label)
        _require_exact_fields(values, GALLERY_IMAGE_FIELDS, label)
        filename = values["file"]
        if not isinstance(filename, str) or not filename.strip():
            raise CommandError(f"{label}.file deve ser um nome de arquivo.")
        if Path(filename).name != filename:
            raise CommandError(f"{label}.file deve conter somente o nome do arquivo.")
        if filename in seen_files:
            raise CommandError(f"gallery_images contém o arquivo duplicado {filename}.")
        seen_files.add(filename)

        path = SEED_ROOT / "media" / "gallery" / filename
        if not path.is_file():
            raise CommandError(f"Arquivo de seed não encontrado: {path}.")

        metadata = {field: values[field] for field in metadata_fields}
        instance = LabGalleryImage(display_order=order, **metadata)
        _validate_model(instance, label, exclude={"image"})
        try:
            with path.open("rb") as source:
                validate_labcompap_image(File(source, name=filename))
        except (OSError, ValidationError) as error:
            if isinstance(error, ValidationError):
                raise _command_error(label, error) from error
            raise CommandError(
                f"Não foi possível ler o arquivo de seed {path}: {error}."
            ) from error

        normalized.append(
            SeedImage(
                path=path,
                values={**_model_values(instance, metadata_fields), "display_order": order},
            )
        )

    return normalized


def load_seed_payload() -> SeedPayload:
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CommandError(f"Manifesto de seed não encontrado: {MANIFEST_PATH}.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(f"Não foi possível ler o manifesto {MANIFEST_PATH}: {error}.") from error

    root = _require_mapping(raw, "data.json")
    _require_exact_fields(root, ROOT_FIELDS, "data.json")
    return SeedPayload(
        equipment=_normalize_equipment(root["equipment"]),
        gallery_images=_normalize_images(root["gallery_images"]),
    )


class Command(BaseCommand):
    help = "Cria o acervo administrável inicial do LabCompAp."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Substitui equipamentos e galeria existentes pelos dados iniciais.",
        )

    def handle(self, *args, **options) -> None:
        payload = load_seed_payload()
        force = options["force"]
        has_content = LabEquipment.objects.exists() or LabGalleryImage.objects.exists()
        if has_content and not force:
            self.stdout.write(
                self.style.WARNING(
                    "O acervo do LabCompAp já existe; nenhuma alteração foi realizada."
                )
            )
            return

        old_files = self._collect_files() if force else []
        created_files: list[tuple[Storage, str]] = []

        try:
            with transaction.atomic():
                if force:
                    LabEquipment.objects.all().delete()
                    LabGalleryImage.objects.all().delete()

                LabEquipment.objects.bulk_create(
                    LabEquipment(**values) for values in payload.equipment
                )
                self._save_images(payload.gallery_images, created_files)
                transaction.on_commit(lambda: self._delete_files(old_files))
        except Exception:
            self._delete_files(created_files)
            raise

        self.stdout.write(
            self.style.SUCCESS(
                "Acervo inicial do LabCompAp criado: "
                f"{len(payload.equipment)} equipamentos e "
                f"{len(payload.gallery_images)} imagens de galeria."
            )
        )

    @staticmethod
    def _collect_files() -> list[tuple[Storage, str]]:
        return [
            (item.image.storage, item.image.name)
            for item in LabGalleryImage.objects.all()
            if item.image.name
        ]

    @staticmethod
    def _save_images(
        images: list[SeedImage],
        created_files: list[tuple[Storage, str]],
    ) -> None:
        for image in images:
            item = LabGalleryImage(**image.values)
            with image.path.open("rb") as source:
                item.image.save(image.path.name, File(source), save=False)
            created_files.append((item.image.storage, item.image.name))
            item.save()

    def _delete_files(self, files: list[tuple[Storage, str]]) -> None:
        for storage, name in files:
            try:
                storage.delete(name)
            except OSError as error:
                self.stderr.write(
                    self.style.WARNING(f"Não foi possível remover a mídia {name}: {error}.")
                )
