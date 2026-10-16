from io import BytesIO
from pathlib import PurePath

from django.core.exceptions import ValidationError
from django.core.files import File
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
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


def webp_image(content):
    """Export a full-size, upright WebP without recompressing existing WebP assets."""
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


def validate_content_image(upload: File, *, label: str) -> None:
    if upload.size > MAX_IMAGE_SIZE:
        raise ValidationError(f"{label} deve ter no máximo 5 MiB.", code="file_too_large")

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

    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError(
            f"{label} deve ter no máximo 20 megapixels.",
            code="too_many_pixels",
        )
