from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


ALLOWED_INGEST_UPLOAD_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xlsm",
    ".xltx",
    ".xltm",
}
ALLOWED_SUPPORT_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
}


def _validate_uploaded_file(
    uploaded_file,
    *,
    allowed_extensions: set[str],
    max_bytes: int,
    label: str,
) -> None:
    if not uploaded_file:
        return

    extension = Path(getattr(uploaded_file, "name", "") or "").suffix.lower()
    if extension not in allowed_extensions:
        allowed_labels = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            f"{label}: extension no permitida. Formatos aceptados: {allowed_labels}."
        )

    file_size = getattr(uploaded_file, "size", 0) or 0
    if file_size <= 0:
        raise ValidationError(f"{label}: el archivo esta vacio.")

    if max_bytes and file_size > max_bytes:
        max_megabytes = max_bytes / (1024 * 1024)
        raise ValidationError(
            f"{label}: supera el tamano maximo permitido de {max_megabytes:.1f} MB."
        )


def validate_ingest_upload(uploaded_file) -> None:
    _validate_uploaded_file(
        uploaded_file,
        allowed_extensions=ALLOWED_INGEST_UPLOAD_EXTENSIONS,
        max_bytes=getattr(settings, "MAX_INGEST_UPLOAD_BYTES", 0),
        label="Archivo de carga",
    )


def validate_support_image(uploaded_file) -> None:
    _validate_uploaded_file(
        uploaded_file,
        allowed_extensions=ALLOWED_SUPPORT_IMAGE_EXTENSIONS,
        max_bytes=getattr(settings, "MAX_SUPPORT_IMAGE_BYTES", 0),
        label="Adjunto de respaldo",
    )
