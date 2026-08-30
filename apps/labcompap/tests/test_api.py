from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.labcompap.models import LabEquipment, LabGalleryImage


def webp_upload(filename: str = "lab.webp") -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#059669").save(buffer, format="WEBP")
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type="image/webp")


@pytest.mark.django_db
def test_api_requires_valid_language_and_returns_empty_collections(client) -> None:
    assert client.get("/api/v1/labcompap").status_code == 422
    assert client.get("/api/v1/labcompap", {"lang": "fr"}).status_code == 422

    response = client.get("/api/v1/labcompap", {"lang": "pt-br"})

    assert response.status_code == 200
    assert response.json() == {"equipment": [], "gallery": []}


@pytest.mark.django_db
def test_api_returns_localized_ordered_content_and_relative_media(
    client, settings, tmp_path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    LabEquipment.objects.create(
        inventory_code="ABC-1",
        name_pt_br="Computador",
        name_en="Computer",
        brand="Apple",
        model_name="iMac",
    )
    LabGalleryImage.objects.create(
        image=webp_upload("gallery.webp"),
        alt_text_pt_br="Galeria",
        alt_text_en="Gallery",
        caption_pt_br="Espaço do laboratório",
        caption_en="Laboratory space",
    )

    response = client.get("/api/v1/labcompap", {"lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"equipment", "gallery"}
    assert body["equipment"][0]["name"] == "Computer"
    assert body["gallery"][0]["alt"] == "Gallery"
    assert body["gallery"][0]["caption"] == "Laboratory space"
    assert body["gallery"][0]["url"].startswith("/media/labcompap/gallery/")
