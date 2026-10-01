import pytest
from fastapi.testclient import TestClient

from mock_server.app import create_app


@pytest.fixture
def mock_client(tmp_path):
    return TestClient(create_app(str(tmp_path / "mocklogs")), base_url="http://mock")
