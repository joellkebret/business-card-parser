from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from conftest import vcard


def upload(client, endpoint='parse', content=None, filename='contact.vcf'):
    return client.post(f'/api/v1/cards/{endpoint}', files={'file': (filename, content if content is not None else vcard('FN:Jane Doe'), 'text/vcard')})


def test_health_docs(client):
    assert client.get('/health').json() == {'status': 'ok', 'native_parser': 'ready', 'persistence': 'sqlite'}
    assert client.get('/docs').status_code == 200
    assert '/api/v1/cards/parse' in client.get('/openapi.json').json()['paths']


def test_ui_and_static_assets(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert 'Contact workspace' in response.text
    assert "script-src 'self'" in response.headers['content-security-policy']
    for asset, content_type in [('app.js', 'javascript'), ('styles.css', 'text/css')]:
        asset_response = client.get(f'/static/{asset}')
        assert asset_response.status_code == 200
        assert content_type in asset_response.headers['content-type']
    assert client.get('/static/../main.py').status_code == 404


def test_parse_validate_without_saving(client):
    response = upload(client)
    assert response.status_code == 200
    assert response.json()['formatted_name'] == 'Jane Doe'
    assert upload(client, 'validate').json() == {'valid': True}
    assert client.get('/api/v1/cards').json() == []


def test_crud(client):
    response = client.post('/api/v1/cards', json={'formatted_name': 'Jane Doe'})
    assert response.status_code == 201
    card = response.json()
    path = response.headers['location']
    assert client.get(path).json() == card
    assert client.get('/api/v1/cards').json() == [card]
    edited = client.patch(path, json={'formatted_name': 'Jane Smith'})
    assert edited.status_code == 200
    assert edited.json()['formatted_name'] == 'Jane Smith'
    assert edited.json()['created_at'] == card['created_at']
    assert client.get(path).json() == edited.json()
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.delete(path).status_code == 404


def test_errors(client):
    cases = [({}, 422), ({'formatted_name': ''}, 422), ({'formatted_name': ' \t'}, 422),
             ({'formatted_name': 'A\r\nEMAIL:injected'}, 422),
             ({'formatted_name': 'A', 'birthday': '20000101'}, 422)]
    for body, status in cases:
        response = client.post('/api/v1/cards', json=body)
        assert response.status_code == status
        assert response.json()['error']['code'] == 'validation_error'
    assert client.get('/api/v1/cards/not-a-uuid').status_code == 422
    assert client.patch(f'/api/v1/cards/{uuid4()}', json={'formatted_name': 'A'}).status_code == 404
    assert client.get('/api/v1/cards?limit=101').status_code == 422
    assert client.get('/missing').json()['error']['code'] == 'http_error'


def test_upload_errors(client):
    for filename in ['card.txt', '../escape.vcf', '..\\escape.vcf', '/tmp/escape.vcf']:
        assert upload(client, filename=filename).status_code == 415
    assert upload(client, content=vcard('FN:A', 'BDAY:20230229')).json()['error']['code'] == 'invalid_datetime'
    assert upload(client, content=b'garbage').status_code == 422
    assert client.post('/api/v1/cards/parse').status_code == 422
    assert upload(client, content=b'x' * 4097).status_code == 413
    assert upload(client, content=b'x' * 100000).status_code == 413
    # Unknown-length request bodies are bounded too.
    response = client.post('/api/v1/cards', content=iter([b'x' * 40000, b'x' * 40000]), headers={'content-type': 'application/json'})
    assert response.status_code == 413


def test_optional_persistence():
    with TestClient(create_app(Settings(database_url='disabled'))) as client:
        assert client.get('/').status_code == 200
        assert upload(client).status_code == 200
        assert upload(client, 'validate').status_code == 200
        assert client.get('/health').json()['persistence'] == 'disabled'
        assert client.get('/api/v1/cards').status_code == 503


def test_persistence_across_app_instances(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path / "cards.db"}')
    with TestClient(create_app(settings)) as client:
        card = client.post('/api/v1/cards', json={'formatted_name': 'Persisted'}).json()
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/v1/cards/{card["id"]}').json() == card


def test_database_failure_is_structured(client, monkeypatch):
    import sqlite3

    def fail(*args):
        raise sqlite3.OperationalError('private database path')

    monkeypatch.setattr(client.app.state.service.repository, 'list', fail)
    response = client.get('/api/v1/cards')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'database_error'
    assert 'private' not in response.text
