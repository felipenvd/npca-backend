from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.projects.validators import validate_project_cover


def image_upload(
    *,
    filename: str = "cover.webp",
    image_format: str = "WEBP",
    content_type: str = "image/webp",
) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "#00bab3").save(buffer, format=image_format)
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type=content_type)


def test_accepts_valid_jpeg_png_and_webp() -> None:
    validate_project_cover(image_upload())
    validate_project_cover(
        image_upload(filename="cover.png", image_format="PNG", content_type="image/png")
    )
    validate_project_cover(
        image_upload(filename="cover.jpg", image_format="JPEG", content_type="image/jpeg")
    )


def test_rejects_svg_invalid_and_mismatched_files() -> None:
    svg = SimpleUploadedFile(
        "cover.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        content_type="image/svg+xml",
    )
    with pytest.raises(ValidationError, match="não é uma imagem válida"):
        validate_project_cover(svg)

    invalid = SimpleUploadedFile("cover.webp", b"not image", content_type="image/webp")
    with pytest.raises(ValidationError, match="não é uma imagem válida"):
        validate_project_cover(invalid)

    with pytest.raises(ValidationError, match="extensão"):
        validate_project_cover(image_upload(filename="cover.png"))


def test_rejects_oversized_file_and_image() -> None:
    upload = MagicMock()
    upload.size = 5 * 1024 * 1024 + 1
    with pytest.raises(ValidationError, match="5 MiB"):
        validate_project_cover(upload)

    upload = SimpleUploadedFile("cover.png", b"image", content_type="image/png")
    opened_image = MagicMock()
    opened_image.__enter__.return_value.format = "PNG"
    opened_image.__enter__.return_value.size = (5000, 5000)
    with (
        patch("apps.core.images.Image.open", return_value=opened_image),
        pytest.raises(ValidationError, match="20 megapixels"),
    ):
        validate_project_cover(upload)
