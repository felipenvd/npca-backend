from pathlib import PurePath

from django.core.exceptions import ValidationError
from django.core.files import File

MAX_PUBLICATION_FILE_SIZE = 20 * 1024 * 1024


def validate_publication_file(upload: File) -> None:
    if upload.size > MAX_PUBLICATION_FILE_SIZE:
        raise ValidationError(
            "O arquivo da publicação deve ter no máximo 20 MiB.",
            code="file_too_large",
        )

    if PurePath(upload.name).suffix.lower() != ".pdf":
        raise ValidationError("Envie a publicação em formato PDF.", code="unsupported_format")

    content_type = getattr(upload, "content_type", None)
    if content_type and content_type != "application/pdf":
        raise ValidationError(
            "O tipo MIME do arquivo deve ser application/pdf.",
            code="mime_mismatch",
        )

    original_position = upload.tell()
    try:
        upload.seek(0)
        signature = upload.read(5)
    finally:
        upload.seek(original_position)

    if signature != b"%PDF-":
        raise ValidationError("O arquivo enviado não é um PDF válido.", code="invalid_pdf")
