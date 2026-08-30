from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.labcompap.validators import validate_labcompap_image


def test_accepts_valid_image_and_rejects_invalid_file() -> None:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#059669").save(buffer, format="WEBP")
    valid = SimpleUploadedFile("lab.webp", buffer.getvalue(), content_type="image/webp")
    validate_labcompap_image(valid)

    invalid = SimpleUploadedFile("lab.webp", b"not an image", content_type="image/webp")
    with pytest.raises(ValidationError, match="imagem válida"):
        validate_labcompap_image(invalid)
