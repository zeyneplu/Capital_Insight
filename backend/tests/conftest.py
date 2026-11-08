from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.sources.fixtures import ALEX


@pytest.fixture
def alex():
    return ALEX


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, data_source="fixtures", nvidia_api_key=None)
    with TestClient(create_app(settings)) as c:  # `with` runs the lifespan
        yield c
