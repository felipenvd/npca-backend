from django.core.files import File

from apps.core.images import validate_content_image


def validate_researcher_photo(upload: File) -> None:
    validate_content_image(upload, label="A foto")
