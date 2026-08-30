import json
import shutil
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image

from apps.labcompap.management.commands import seed_labcompap
from apps.labcompap.models import LabEquipment, LabGalleryImage


@pytest.fixture
def isolated_seed_package(tmp_path, monkeypatch) -> Path:
    target = tmp_path / "seed" / "labcompap"
    shutil.copytree(seed_labcompap.SEED_ROOT, target)
    monkeypatch.setattr(seed_labcompap, "SEED_ROOT", target)
    monkeypatch.setattr(seed_labcompap, "MANIFEST_PATH", target / "data.json")
    return target


def read_manifest(seed_root: Path) -> dict:
    return json.loads((seed_root / "data.json").read_text(encoding="utf-8"))


def write_manifest(seed_root: Path, manifest: dict) -> None:
    (seed_root / "data.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.django_db
def test_seed_creates_real_content_and_is_idempotent(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    output = StringIO()

    call_command("seed_labcompap", stdout=output)

    assert LabGalleryImage.objects.count() == 9
    assert LabEquipment.objects.count() == 10
    assert "10 equipamentos" in output.getvalue()
    assert "9 imagens de galeria" in output.getvalue()

    images = list(LabGalleryImage.objects.all())
    for item in images:
        path = Path(item.image.path)
        assert path.is_file()
        with Image.open(path) as image:
            image.verify()

    equipment = LabEquipment.objects.first()
    assert equipment is not None
    equipment.name_pt_br = "Alteração editorial preservada"
    equipment.save()
    call_command("seed_labcompap")
    equipment.refresh_from_db()

    assert equipment.name_pt_br == "Alteração editorial preservada"
    assert LabEquipment.objects.count() == 10
    assert LabGalleryImage.objects.count() == 9


@pytest.mark.django_db(transaction=True)
def test_force_replaces_content_and_removes_old_media_after_commit(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_labcompap")
    old_files = {Path(item.image.path) for item in LabGalleryImage.objects.all()}
    equipment = LabEquipment.objects.first()
    assert equipment is not None
    equipment.name_pt_br = "Conteúdo editorial substituível"
    equipment.save()

    call_command("seed_labcompap", force=True)

    assert not LabEquipment.objects.filter(name_pt_br="Conteúdo editorial substituível").exists()
    assert all(not path.exists() for path in old_files)
    new_files = {Path(item.image.path) for item in LabGalleryImage.objects.all()}
    assert len(new_files) == 9
    assert all(path.is_file() for path in new_files)
    assert new_files.isdisjoint(old_files)


@pytest.mark.django_db
def test_invalid_json_fails_before_database_or_media_writes(
    settings,
    tmp_path,
    isolated_seed_package,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    (isolated_seed_package / "data.json").write_text("{invalid", encoding="utf-8")

    with pytest.raises(CommandError, match="Não foi possível ler o manifesto"):
        call_command("seed_labcompap")

    assert LabEquipment.objects.count() == 0
    assert LabGalleryImage.objects.count() == 0
    assert not settings.MEDIA_ROOT.exists()


@pytest.mark.django_db
def test_missing_asset_fails_before_database_or_media_writes(
    settings,
    tmp_path,
    isolated_seed_package,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    (isolated_seed_package / "media" / "gallery" / "image_01.webp").unlink()

    with pytest.raises(CommandError, match="Arquivo de seed não encontrado"):
        call_command("seed_labcompap")

    assert LabEquipment.objects.count() == 0
    assert LabGalleryImage.objects.count() == 0
    assert not settings.MEDIA_ROOT.exists()


@pytest.mark.django_db
def test_invalid_manifest_content_fails_before_writes(
    settings,
    tmp_path,
    isolated_seed_package,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    manifest = read_manifest(isolated_seed_package)
    manifest["equipment"][1]["inventory_code"] = manifest["equipment"][0]["inventory_code"]
    write_manifest(isolated_seed_package, manifest)

    with pytest.raises(CommandError, match="códigos de inventário duplicados"):
        call_command("seed_labcompap")

    assert LabEquipment.objects.count() == 0
    assert LabGalleryImage.objects.count() == 0
    assert not settings.MEDIA_ROOT.exists()


@pytest.mark.django_db
def test_storage_files_are_compensated_when_database_seed_fails(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    original = seed_labcompap.Command._save_images

    def fail_after_first_image(images, created_files) -> None:
        original(images[:1], created_files)
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(
        seed_labcompap.Command,
        "_save_images",
        staticmethod(fail_after_first_image),
    )

    with pytest.raises(RuntimeError, match="falha simulada"):
        call_command("seed_labcompap")

    assert LabEquipment.objects.count() == 0
    assert LabGalleryImage.objects.count() == 0
    assert not [path for path in settings.MEDIA_ROOT.rglob("*") if path.is_file()]
