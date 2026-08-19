import os

os.environ["EXPEDIENTE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["EXPEDIENTE_BOOTSTRAP_TOKEN"] = "test-bootstrap-secret"

import pytest  # noqa: E402

from expediente_pr.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EXPEDIENTE_DOCUMENT_ROOT", str(tmp_path / "quarantine"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
