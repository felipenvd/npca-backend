from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.researchers.validators import validate_researcher_photo


def image_upload(
    *,
    filename: str = "photo.webp",
    image_format: str = "WEBP",
    content_type: str = "image/webp",
) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "#00bab3").save(buffer, format=image_format)
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type=content_type)


def test_accepts_valid_jpeg_png_and_webp() -> None:
    validate_researcher_photo(image_upload())
    validate_researcher_photo(
        image_upload(filename="photo.png", image_format="PNG", content_type="image/png")
    )
    validate_researcher_photo(
        image_upload(filename="photo.jpg", image_format="JPEG", content_type="image/jpeg")
    )


def test_rejects_invalid_and_mismatched_files() -> None:
    invalid = SimpleUploadedFile("photo.webp", b"not an image", content_type="image/webp")
    with pytest.raises(ValidationError, match="não é uma imagem válida"):
        validate_researcher_photo(invalid)

    with pytest.raises(ValidationError, match="extensão"):
        validate_researcher_photo(image_upload(filename="photo.png"))


def test_rejects_oversized_file() -> None:
    upload = MagicMock()
    upload.size = 5 * 1024 * 1024 + 1

    with pytest.raises(ValidationError, match="5 MiB"):
        validate_researcher_photo(upload)


def test_rejects_image_over_twenty_megapixels() -> None:
    upload = SimpleUploadedFile("photo.png", b"image", content_type="image/png")
    opened_image = MagicMock()
    opened_image.__enter__.return_value.format = "PNG"
    opened_image.__enter__.return_value.size = (5000, 5000)

    with (
        patch("apps.core.images.Image.open", return_value=opened_image),
        pytest.raises(ValidationError, match="20 megapixels"),
    ):
        validate_researcher_photo(upload)
