import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": (b"%PDF-", ".pdf"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        b"PK",
        ".docx",
    ),
}


class UnsafeDocumentError(ValueError):
    pass


def _storage_root() -> Path:
    root = Path(os.getenv("EXPEDIENTE_DOCUMENT_ROOT", "./data/quarantine")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_quarantined(content: bytes, media_type: str) -> tuple[str, str]:
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise UnsafeDocumentError("El archivo está vacío o excede 20 MB")
    expected = ALLOWED_TYPES.get(media_type)
    if expected is None or not content.startswith(expected[0]):
        raise UnsafeDocumentError("El contenido no coincide con un PDF o DOCX permitido")
    digest = hashlib.sha256(content).hexdigest()
    storage_key = f"{uuid4()}{expected[1]}"
    target = _storage_root() / storage_key
    target.write_bytes(content)
    return storage_key, digest


def export_to_velum(storage_key: str) -> Path:
    configured = os.getenv("EXPEDIENTE_VELUM_ROOT")
    if not configured:
        raise UnsafeDocumentError("EXPEDIENTE_VELUM_ROOT no está configurado")
    root = Path(configured).resolve(strict=True)
    if not root.is_dir():
        raise UnsafeDocumentError("La raíz de VELUM no es un directorio")
    source = (_storage_root() / storage_key).resolve(strict=True)
    if source.parent != _storage_root():
        raise UnsafeDocumentError("Clave de almacenamiento inválida")
    target = root / source.name
    shutil.copyfile(source, target)
    return target
