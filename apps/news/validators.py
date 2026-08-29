from pathlib import PurePath

from django.core.exceptions import ValidationError
from django.core.files import File
from PIL import Image, UnidentifiedImageError

MAX_COVER_SIZE = 5 * 1024 * 1024
MAX_COVER_PIXELS = 20_000_000
FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
}
FORMAT_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def validate_news_cover(upload: File) -> None:
    if upload.size > MAX_COVER_SIZE:
        raise ValidationError("A imagem de capa deve ter no máximo 5 MiB.", code="file_too_large")

    extension = PurePath(upload.name).suffix.lower()
    original_position = upload.tell()

    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (OSError, UnidentifiedImageError, SyntaxError) as exc:
        raise ValidationError(
            "O arquivo enviado não é uma imagem válida.", code="invalid_image"
        ) from exc
    finally:
        upload.seek(original_position)

    if image_format not in FORMAT_EXTENSIONS:
        raise ValidationError("Use uma imagem JPEG, PNG ou WebP.", code="unsupported_format")

    if extension not in FORMAT_EXTENSIONS[image_format]:
        raise ValidationError(
            "A extensão do arquivo não corresponde ao formato da imagem.",
            code="extension_mismatch",
        )

    content_type = getattr(upload, "content_type", None)
    if content_type and content_type != FORMAT_MIME_TYPES[image_format]:
        raise ValidationError(
            "O tipo MIME não corresponde ao formato da imagem.",
            code="mime_mismatch",
        )

    if width * height > MAX_COVER_PIXELS:
        raise ValidationError(
            "A imagem de capa deve ter no máximo 20 megapixels.",
            code="too_many_pixels",
        )
