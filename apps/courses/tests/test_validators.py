from io import BytesIO
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.courses.validators import validate_course_cover, validate_https_url


def webp_upload() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#00bab3").save(buffer, format="WEBP")
    return SimpleUploadedFile("course.webp", buffer.getvalue(), content_type="image/webp")


def test_accepts_valid_cover_and_https_url() -> None:
    validate_course_cover(webp_upload())
    validate_https_url("https://example.com/course")


def test_rejects_invalid_cover_and_http_url() -> None:
    invalid = SimpleUploadedFile("course.webp", b"not an image", content_type="image/webp")
    with pytest.raises(ValidationError, match="não é uma imagem válida"):
        validate_course_cover(invalid)
    with pytest.raises(ValidationError, match="https://"):
        validate_https_url("http://example.com/course")


def test_rejects_oversized_cover() -> None:
    upload = MagicMock()
    upload.size = 5 * 1024 * 1024 + 1

    with pytest.raises(ValidationError, match="5 MiB"):
        validate_course_cover(upload)
