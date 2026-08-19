import pytest

from expediente_pr.store import store


@pytest.fixture(autouse=True)
def reset_store() -> None:
    store.clear()

