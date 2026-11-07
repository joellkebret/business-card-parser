"""Exercise a running service over HTTP without extra dependencies."""
import argparse
import json
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()

    def request(path, method='GET', body=None, content_type='application/json'):
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        with urlopen(Request(args.url + path, data=data, method=method,
                             headers={'Content-Type': content_type}), timeout=10) as response:
            content = response.read()
            return response.status, json.loads(content) if content and 'application/json' in response.headers.get('content-type', '') else content

    assert request('/health')[1]['status'] == 'ok'
    assert request('/')[0] == 200
    assert request('/static/app.js')[0] == 200
    assert request('/static/styles.css')[0] == 200
    assert request('/docs')[0] == 200
    assert request('/openapi.json')[0] == 200
    card = b'BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Smoke Test\r\nEND:VCARD\r\n'
    multipart = (b'--smoke-boundary\r\nContent-Disposition: form-data; name="file"; filename="test.vcf"\r\n'
                 b'Content-Type: text/vcard\r\n\r\n' + card + b'\r\n--smoke-boundary--\r\n')
    for action in ('parse', 'validate'):
        assert request(f'/api/v1/cards/{action}', 'POST', multipart, 'multipart/form-data; boundary=smoke-boundary')[0] == 200
    status, created = request('/api/v1/cards', 'POST', {'formatted_name': 'Smoke Test'})
    assert status == 201
    path = f'/api/v1/cards/{created["id"]}'
    try:
        assert request(path)[1]['formatted_name'] == 'Smoke Test'
        assert request('/api/v1/cards')[0] == 200
        assert request(path, 'PATCH', {'formatted_name': 'Updated Smoke Test'})[1]['formatted_name'] == 'Updated Smoke Test'
    finally:
        assert request(path, 'DELETE')[0] == 204
    print('HTTP smoke test passed: UI assets, health, docs, OpenAPI, parse, validate, create, list, read, update, delete')


if __name__ == '__main__':
    main()
