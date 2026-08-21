import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_DOCX_MEMBERS = 2_000
MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
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
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError as exc:
        raise UnsafeDocumentError("No se pudieron asegurar los permisos de cuarentena") from exc
    return root


def _validate_pdf(content: bytes) -> None:
    if not content.rstrip().endswith(b"%%EOF"):
        raise UnsafeDocumentError("El PDF está truncado o no tiene marcador EOF")
    lowered = content.lower()
    for marker in (b"/javascript", b"/js", b"/launch", b"/embeddedfile", b"/richmedia"):
        if marker in lowered:
            raise UnsafeDocumentError("El PDF contiene contenido activo o adjunto no permitido")


def _validate_docx(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                raise UnsafeDocumentError("El DOCX contiene demasiadas partes")
            total = 0
            names: set[str] = set()
            for member in members:
                path = Path(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise UnsafeDocumentError("El DOCX contiene una ruta interna insegura")
                total += member.file_size
                if total > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise UnsafeDocumentError("El DOCX excede el límite descomprimido")
                names.add(member.filename.lower())
            required = {"[content_types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise UnsafeDocumentError("El archivo no es un DOCX válido")
            if any(name.endswith("vbaproject.bin") for name in names):
                raise UnsafeDocumentError("Los documentos con macros no están permitidos")
            for name in names:
                if not name.endswith(".rels"):
                    continue
                relationship_xml = archive.read(name).lower()
                if b'targetmode="external"' in relationship_xml:
                    raise UnsafeDocumentError("El DOCX contiene relaciones externas")
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise UnsafeDocumentError("El archivo no es un DOCX seguro") from exc


def _validate_content(content: bytes, media_type: str) -> str:
    expected = ALLOWED_TYPES.get(media_type)
    if expected is None or not content.startswith(expected[0]):
        raise UnsafeDocumentError("El contenido no coincide con un PDF o DOCX permitido")
    if media_type == "application/pdf":
        _validate_pdf(content)
    else:
        _validate_docx(content)
    return expected[1]


def _write_exclusive(target: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
    except OSError as exc:
        raise UnsafeDocumentError("No se pudo crear el archivo de forma segura") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise


def save_quarantined(content: bytes, media_type: str) -> tuple[str, str]:
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise UnsafeDocumentError("El archivo está vacío o excede 20 MB")
    suffix = _validate_content(content, media_type)
    digest = hashlib.sha256(content).hexdigest()
    storage_key = f"{uuid4()}{suffix}"
    _write_exclusive(_storage_root() / storage_key, content)
    return storage_key, digest


def export_to_velum(storage_key: str) -> Path:
    configured = os.getenv("EXPEDIENTE_VELUM_ROOT")
    if not configured:
        raise UnsafeDocumentError("EXPEDIENTE_VELUM_ROOT no está configurado")
    root = Path(configured).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise UnsafeDocumentError("La raíz de VELUM no es un directorio seguro")
    source = (_storage_root() / storage_key).resolve(strict=True)
    if source.parent != _storage_root() or not source.is_file() or source.is_symlink():
        raise UnsafeDocumentError("Clave de almacenamiento inválida")
    target = root / source.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
