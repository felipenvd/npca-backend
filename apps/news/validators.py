from django.core.files import File

from apps.core.images import validate_content_image


def validate_news_cover(upload: File) -> None:
    validate_content_image(upload, label="A imagem de capa")
