from django.core.files import File

from apps.core.images import validate_content_image


def validate_labcompap_image(upload: File) -> None:
    validate_content_image(upload, label="A imagem do LabCompAp")
