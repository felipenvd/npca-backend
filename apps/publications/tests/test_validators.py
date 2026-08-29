from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.publications.validators import validate_publication_file


def test_accepts_pdf_signature_extension_and_mime() -> None:
    upload = SimpleUploadedFile(
        "paper.pdf",
        b"%PDF-1.7\ncontent",
        content_type="application/pdf",
    )
    validate_publication_file(upload)


@pytest.mark.parametrize(
    ("name", "content", "content_type", "message"),
    [
        ("paper.txt", b"%PDF-1.7", "application/pdf", "formato PDF"),
        ("paper.pdf", b"not a pdf", "application/pdf", "não é um PDF"),
        ("paper.pdf", b"%PDF-1.7", "text/plain", "tipo MIME"),
    ],
)
def test_rejects_invalid_publication_files(
    name: str,
    content: bytes,
    content_type: str,
    message: str,
) -> None:
    upload = SimpleUploadedFile(name, content, content_type=content_type)
    with pytest.raises(ValidationError, match=message):
        validate_publication_file(upload)


def test_rejects_file_larger_than_limit() -> None:
    upload = SimpleUploadedFile(
        "paper.pdf",
        BytesIO(b"%PDF-" + b"0" * (20 * 1024 * 1024)).getvalue(),
        content_type="application/pdf",
    )
    with pytest.raises(ValidationError, match="20 MiB"):
        validate_publication_file(upload)
