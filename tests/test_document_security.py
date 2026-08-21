import io
import zipfile
from pathlib import Path

import pytest

from expediente_pr.document_storage import UnsafeDocumentError, save_quarantined


def _docx(*, external: bool = False, macro: bool = False) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
        if external:
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships><Relationship TargetMode="External" Target="https://example.test"/></Relationships>',
            )
        if macro:
            archive.writestr("word/vbaProject.bin", b"macro")
    return stream.getvalue()


def test_quarantine_uses_private_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXPEDIENTE_DOCUMENT_ROOT", str(tmp_path / "quarantine"))
    key, _ = save_quarantined(
        _docx(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert ((tmp_path / "quarantine" / key).stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize("content", [_docx(external=True), _docx(macro=True)])
def test_rejects_active_docx(tmp_path: Path, monkeypatch, content: bytes) -> None:
    monkeypatch.setenv("EXPEDIENTE_DOCUMENT_ROOT", str(tmp_path / "quarantine"))
    with pytest.raises(UnsafeDocumentError):
        save_quarantined(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def test_rejects_active_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXPEDIENTE_DOCUMENT_ROOT", str(tmp_path / "quarantine"))
    with pytest.raises(UnsafeDocumentError):
        save_quarantined(b"%PDF-1.7\n/JavaScript\n%%EOF", "application/pdf")
