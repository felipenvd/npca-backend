from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.events.validators import validate_event_cover


def test_accepts_valid_event_cover() -> None:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), "#00bab3").save(buffer, format="WEBP")
    upload = SimpleUploadedFile(
        "event.webp",
        buffer.getvalue(),
        content_type="image/webp",
    )

    validate_event_cover(upload)
