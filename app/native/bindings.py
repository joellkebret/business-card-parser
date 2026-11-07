"""ctypes ABI definitions. Native pointers never leave this module.

createCard owns failure cleanup; on success _card owns exactly one deleteCard.
All data is copied into Python values before leaving the context manager.
The lock protects the legacy parser's use of strtok across worker threads.
"""
from contextlib import contextmanager
import ctypes as C
import os
from pathlib import Path
import tempfile
import threading

from app.core.errors import NativeError, ServiceError
from app.schemas.cards import ParsedCard


class Node(C.Structure):
    pass


Node._fields_ = [('data', C.c_void_p), ('previous', C.POINTER(Node)), ('next', C.POINTER(Node))]


class List(C.Structure):
    _fields_ = [('head', C.POINTER(Node)), ('tail', C.POINTER(Node)), ('length', C.c_int),
                ('deleteData', C.c_void_p), ('compare', C.c_void_p), ('printData', C.c_void_p)]


class Parameter(C.Structure):
    _fields_ = [('name', C.c_char_p), ('value', C.c_char_p)]


class Property(C.Structure):
    _fields_ = [('name', C.c_char_p), ('group', C.c_char_p), ('parameters', C.POINTER(List)), ('values', C.POINTER(List))]


class DateTime(C.Structure):
    _fields_ = [('UTC', C.c_bool), ('isText', C.c_bool), ('date', C.c_char_p), ('time', C.c_char_p), ('text', C.c_char_p)]


class Card(C.Structure):
    _fields_ = [('fn', C.POINTER(Property)), ('optionalProperties', C.POINTER(List)),
                ('birthday', C.POINTER(DateTime)), ('anniversary', C.POINTER(DateTime))]


_NATIVE_LOCK = threading.RLock()


def _text(value):
    return value.decode('utf-8') if value else ''


def _items(pointer):
    node = pointer.contents.head
    while node:
        yield node.contents.data
        node = node.contents.next


def _property(pointer):
    prop = pointer.contents
    return dict(name=_text(prop.name), group=_text(prop.group),
                values=[_text(C.cast(item, C.c_char_p).value) for item in _items(prop.values)],
                parameters=[dict(name=_text(p.name), value=_text(p.value))
                            for item in _items(prop.parameters)
                            for p in [C.cast(item, C.POINTER(Parameter)).contents]])


def _date(pointer):
    if not pointer:
        return None
    dt = pointer.contents
    return dict(date=_text(dt.date), time=_text(dt.time), text=_text(dt.text), is_text=dt.isText, utc=dt.UTC)


class NativeParser:
    def __init__(self, library_path: Path):
        try:
            self.lib = C.CDLL(str(library_path.resolve()))
        except OSError as exc:
            raise RuntimeError('Native library unavailable. Run python scripts/build_native.py first.') from exc
        signatures = {
            'createCard': ([C.c_char_p, C.POINTER(C.POINTER(Card))], C.c_int),
            'validateCard': ([C.POINTER(Card)], C.c_int),
            'deleteCard': ([C.POINTER(Card)], None),
            'writeCard': ([C.c_char_p, C.POINTER(Card)], C.c_int),
            'updateFN': ([C.POINTER(Card), C.c_char_p], C.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes = arguments
            function.restype = result

    @staticmethod
    def _check(result):
        if result:
            raise NativeError(result)

    @contextmanager
    def _card(self, path):
        pointer = C.POINTER(Card)()
        self._check(self.lib.createCard(os.fsencode(path), C.byref(pointer)))
        try:
            self._check(self.lib.validateCard(pointer))
            yield pointer
        finally:
            self.lib.deleteCard(pointer)

    def parse(self, content: bytes, formatted_name: str | None = None) -> ParsedCard:
        try:
            content.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ServiceError('invalid_encoding', 'vCard files must be UTF-8.') from exc
        if b'\x00' in content:
            raise ServiceError('invalid_card', 'NUL bytes are not allowed.')
        # Paths are server-generated and private; upload filenames are never used.
        with _NATIVE_LOCK, tempfile.TemporaryDirectory(prefix='vcard-') as directory:
            source = Path(directory) / 'input.vcf'
            destination = Path(directory) / 'output.vcf'
            source.write_bytes(content)
            with self._card(source) as pointer:
                if formatted_name is not None:
                    self._check(self.lib.updateFN(pointer, formatted_name.encode('utf-8')))
                    self._check(self.lib.validateCard(pointer))
                self._check(self.lib.writeCard(os.fsencode(destination), pointer))
                card = pointer.contents
                fn = _property(card.fn)
                return ParsedCard(formatted_name=fn['values'][0], formatted_name_property=fn,
                                  properties=[_property(C.cast(item, C.POINTER(Property))) for item in _items(card.optionalProperties)],
                                  birthday=_date(card.birthday), anniversary=_date(card.anniversary),
                                  vcard=destination.read_bytes().decode('utf-8'))
