from concurrent.futures import ThreadPoolExecutor
import ctypes as C
from pathlib import Path

import pytest

from app.core.errors import NativeError, ServiceError
from app.native.bindings import Card
from app.native.bindings import NativeParser
from conftest import vcard


def test_parse_and_roundtrip(parser):
    content = vcard('item.FN;LANGUAGE=en:Jane Doe', 'N:Doe;Jane;;;',
                    'work.EMAIL;TYPE=work:jane@example.org', 'BDAY:20000229', 'ANNIVERSARY;VALUE=text:circa 2020')
    parsed = parser.parse(content)
    assert parsed.formatted_name == 'Jane Doe'
    assert parsed.properties[1].group == 'work'
    assert parsed.formatted_name_property.parameters[0].name == 'LANGUAGE'
    assert parsed.birthday.date == '20000229'
    assert parsed.anniversary.is_text
    assert parser.parse(parsed.vcard.encode()) == parsed
    edited = parser.parse(parsed.vcard.encode(), formatted_name='New Name')
    assert edited.formatted_name == 'New Name'
    assert edited.formatted_name_property.group == 'item'
    assert edited.formatted_name_property.parameters == parsed.formatted_name_property.parameters
    assert edited.properties == parsed.properties


def test_missing_library(tmp_path):
    with pytest.raises(RuntimeError, match='build_native.py'):
        NativeParser(tmp_path / 'missing-library')


@pytest.mark.parametrize('properties,code', [
    ([], 2), (['FN:'], 3), (['FN:A', 'BDAY:20230229'], 4),
    (['FN:A', 'BDAY:20241301'], 4), (['FN:A', 'BDAY:20240001'], 4),
    (['FN:A', 'BDAY:20240100'], 4), (['FN:A', 'BDAY:20000101T'], 4),
    (['FN:A', 'BDAY:T256000'], 4), (['FN:A', 'BDAY:T'], 4),
    (['FN:A', 'BDAY:20000101', 'BDAY:20010101'], 4),
    (['FN:A', 'ANNIVERSARY:20000101', 'ANNIVERSARY:20010101'], 4),
    (['FN:A', 'X-TEST;BROKEN:value'], 3), (['FN:A', 'N:A;B;C;D;E;F'], 3),
    (['FN;LANGUAGE=:A'], 3),
    (['FN:A', 'REV:20200101T000000Z', 'REV:20210101T000000Z'], 3),
])
def test_invalid(parser, properties, code):
    with pytest.raises(NativeError) as error:
        parser.parse(vcard(*properties))
    assert error.value.native_code == code


@pytest.mark.parametrize('date', ['--0229', '---31', '--12', '1990', 'T143000', '20000101T120000Z'])
def test_supported_dates(parser, date):
    assert parser.parse(vcard('FN:A', f'BDAY:{date}')).birthday


@pytest.mark.parametrize('content', [b'', b'garbage\r\n', vcard('FN:A').replace(b'4.0', b'3.0'),
                                    vcard('FN:A').replace(b'4.0', b'4.0junk'),
                                    vcard('FN:A').replace(b'\r\n', b'\n'),
                                    vcard('FN:A') + vcard('FN:B'),
                                    vcard('FN:A', 'NOTE:' + 'x' * 65536)],
                         ids=['empty', 'garbage', 'version3', 'bad_version', 'lf_only', 'multiple_cards', 'long_line'])
def test_malformed(parser, content):
    with pytest.raises(NativeError):
        parser.parse(content)


@pytest.mark.parametrize('content', [b'\xff', b'\x00'])
def test_invalid_bytes(parser, content):
    with pytest.raises(ServiceError):
        parser.parse(content)


def test_unfolding_and_escaped_structured_values(parser):
    parsed = parser.parse(vcard('FN:Ja\r\n ne', 'N:Doe\\;Family;Jane;;;', 'KEY;VALUE=uri:\r\n https://example.org/key'))
    assert parsed.formatted_name == 'Jane'
    assert parsed.properties[0].values[0] == r'Doe\;Family'
    assert parsed.properties[1].values == ['https://example.org/key']


def test_rev_and_scalar_properties_preserved(parser):
    parsed = parser.parse(vcard('FN:A', 'REV:20200101T000000Z', 'GENDER:M', 'CLIENTPIDMAP:1;urn:uuid:example'))
    assert 'GENDER:M\r\n' in parsed.vcard
    assert 'CLIENTPIDMAP:1;urn:uuid:example\r\n' in parsed.vcard


def test_failure_pointer_is_null(parser, tmp_path):
    source = tmp_path / 'invalid.vcf'
    source.write_bytes(vcard('BDAY:T'))
    pointer = C.POINTER(Card)()
    assert parser.lib.createCard(str(source).encode(), C.byref(pointer)) != 0
    assert not pointer


def test_delete_on_success_and_validation_failure(parser, monkeypatch):
    original = parser.lib.deleteCard
    deleted = []

    def track(pointer):
        deleted.append(True)
        original(pointer)

    monkeypatch.setattr(parser.lib, 'deleteCard', track)
    parser.parse(vcard('FN:A'))
    with pytest.raises(NativeError):
        parser.parse(vcard('FN:A', 'BDAY:20230229'))
    assert len(deleted) == 2


def test_delete_on_write_and_update_failure(parser, monkeypatch):
    original = parser.lib.deleteCard
    deleted = []

    def track(pointer):
        deleted.append(True)
        original(pointer)

    monkeypatch.setattr(parser.lib, 'deleteCard', track)
    monkeypatch.setattr(parser.lib, 'writeCard', lambda *args: 5)
    with pytest.raises(NativeError) as error:
        parser.parse(vcard('FN:A'))
    assert error.value.status == 500
    monkeypatch.setattr(parser.lib, 'updateFN', lambda *args: 6)
    with pytest.raises(NativeError):
        parser.parse(vcard('FN:A'), formatted_name='B')
    assert len(deleted) == 2


def test_parallel_parse(parser):
    with ThreadPoolExecutor(max_workers=8) as pool:
        names = list(pool.map(lambda i: parser.parse(vcard(f'FN:Name {i}', 'EMAIL;TYPE=work:a@example.org')).formatted_name, range(100)))
    assert names == [f'Name {i}' for i in range(100)]


@pytest.mark.parametrize('path', sorted(Path('tests/fixtures/cards').glob('*.vcf')), ids=lambda path: path.stem)
def test_existing_fixtures(parser, path):
    parsed = parser.parse(path.read_bytes())
    assert parser.parse(parsed.vcard.encode()) == parsed
