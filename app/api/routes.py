from pathlib import PurePath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.errors import ServiceError
from app.schemas.cards import CardInput, CardRecord, Health, ParsedCard, ValidationResult

router = APIRouter()


@router.get('/health', response_model=Health)
def health(request: Request):
    return Health(persistence='sqlite' if request.app.state.service.repository else 'disabled')


async def uploaded_card(request, file):
    try:
        # Reject paths even though only server-generated filenames touch disk.
        filename = file.filename or ''
        if '/' in filename or '\\' in filename or PurePath(filename).suffix.lower() not in {'.vcf', '.vcard'}:
            raise ServiceError('unsupported_format', 'Upload a .vcf or .vcard filename without path components.', 415)
        content = await file.read(request.app.state.settings.max_upload_bytes + 1)
        if len(content) > request.app.state.settings.max_upload_bytes:
            raise ServiceError('file_too_large', 'The uploaded file exceeds MAX_UPLOAD_BYTES.', 413)
        return await run_in_threadpool(request.app.state.service.parser.parse, content)
    finally:
        await file.close()


@router.post('/api/v1/cards/parse', response_model=ParsedCard)
async def parse(request: Request, file: Annotated[UploadFile, File()]):
    return await uploaded_card(request, file)


@router.post('/api/v1/cards/validate', response_model=ValidationResult)
async def validate(request: Request, file: Annotated[UploadFile, File()]):
    await uploaded_card(request, file)
    return ValidationResult()


@router.post('/api/v1/cards', response_model=CardRecord, status_code=201)
def create(request: Request, body: CardInput, response: Response):
    card = request.app.state.service.create(body.formatted_name)
    response.headers['Location'] = f'/api/v1/cards/{card.id}'
    return card


@router.get('/api/v1/cards', response_model=list[CardRecord])
def list_cards(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50,
               offset: Annotated[int, Query(ge=0)] = 0):
    return request.app.state.service.list(limit, offset)


@router.get('/api/v1/cards/{card_id}', response_model=CardRecord)
def get(request: Request, card_id: UUID):
    return request.app.state.service.get(str(card_id))


@router.patch('/api/v1/cards/{card_id}', response_model=CardRecord)
def update(request: Request, card_id: UUID, body: CardInput):
    return request.app.state.service.update(str(card_id), body.formatted_name)


@router.delete('/api/v1/cards/{card_id}', status_code=204)
def delete(request: Request, card_id: UUID):
    request.app.state.service.delete(str(card_id))
    return Response(status_code=204)
