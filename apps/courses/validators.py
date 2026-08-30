from django.core.exceptions import ValidationError
from django.core.files import File

from apps.core.images import validate_content_image


def validate_course_cover(upload: File) -> None:
    validate_content_image(upload, label="A imagem de divulgação")


def validate_https_url(value: str) -> None:
    if value and not value.lower().startswith("https://"):
        raise ValidationError(
            "Informe uma URL segura iniciada por https://.",
            code="https_required",
        )
