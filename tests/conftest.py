import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.native.bindings import NativeParser


@pytest.fixture
def parser():
    return NativeParser(Settings().library_path)


@pytest.fixture
def client(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path / "contacts.db"}', max_upload_bytes=4096)
    with TestClient(create_app(settings)) as client:
        yield client


def vcard(*properties):
    return ('BEGIN:VCARD\r\nVERSION:4.0\r\n' + '\r\n'.join(properties) + '\r\nEND:VCARD\r\n').encode('utf-8')
