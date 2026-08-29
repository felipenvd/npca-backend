from django.core.files import File

from apps.core.images import validate_content_image


def validate_event_cover(upload: File) -> None:
    validate_content_image(upload, label="A imagem do evento")
