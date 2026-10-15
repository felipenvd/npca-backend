import math
from io import BytesIO
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

DEFAULT_PHOTO_CROP = {"x": 50, "y": 50, "zoom": 1}


def validate_photo_crop(value):
    if not isinstance(value, dict) or value.keys() - DEFAULT_PHOTO_CROP.keys():
        raise ValidationError("O enquadramento da foto é inválido.")
    for key, default in DEFAULT_PHOTO_CROP.items():
        number = value.get(key, default)
        minimum, maximum = (1, 3) if key == "zoom" else (0, 100)
        if (
            isinstance(number, bool)
            or not isinstance(number, int | float)
            or not math.isfinite(number)
            or not minimum <= number <= maximum
        ):
            raise ValidationError("O enquadramento da foto é inválido.")


def cropped_photo(upload, crop):
    """Keep the original upload and create the square used by every public avatar."""
    validate_photo_crop(crop)
    position = DEFAULT_PHOTO_CROP | crop
    upload.open("rb")
    try:
        with Image.open(upload) as original:
            image = ImageOps.exif_transpose(original)
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            width, height = image.size
            side = min(width, height) / position["zoom"]
            left = (width - side) * position["x"] / 100
            top = (height - side) * position["y"] / 100
            size = min(512, max(1, round(side)))
            image = image.resize(
                (size, size),
                Image.Resampling.LANCZOS,
                box=(left, top, left + side, top + side),
            )
            output = BytesIO()
            image.save(output, "WEBP", quality=90, method=6)
    finally:
        upload.seek(0)
    return ContentFile(output.getvalue(), name=f"{uuid4().hex}.webp")
