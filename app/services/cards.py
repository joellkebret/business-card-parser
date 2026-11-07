from app.core.errors import ServiceError
from app.schemas.cards import CardRecord


class CardService:
    def __init__(self, parser, repository):
        self.parser = parser
        self.repository = repository

    def _repository(self):
        if self.repository is None:
            raise ServiceError('persistence_disabled', 'Contact persistence is disabled.', 503)
        return self.repository

    def _record(self, row):
        parsed = self.parser.parse(row['vcard'].encode('utf-8'))
        return CardRecord(**parsed.model_dump(), **{key: row[key] for key in ('id', 'created_at', 'updated_at')})

    def create(self, name):
        repository = self._repository()
        content = f'BEGIN:VCARD\r\nVERSION:4.0\r\nFN:{name}\r\nEND:VCARD\r\n'.encode('utf-8')
        parsed = self.parser.parse(content)
        return self._record(repository.create(parsed.vcard))

    def get(self, identifier):
        return self._record(self._repository().get(identifier))

    def list(self, limit, offset):
        return [self._record(row) for row in self._repository().list(limit, offset)]

    def update(self, identifier, name):
        repository = self._repository()
        row = repository.get(identifier)
        parsed = self.parser.parse(row['vcard'].encode('utf-8'), formatted_name=name)
        return self._record(repository.update(identifier, parsed.vcard))

    def delete(self, identifier):
        self._repository().delete(identifier)
