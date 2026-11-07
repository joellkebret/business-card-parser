from contextlib import asynccontextmanager
import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.core.config import Settings
from app.core.errors import ServiceError
from app.core.middleware import RequestSizeLimit
from app.native.bindings import NativeParser
from app.schemas.cards import ErrorResponse
from app.services.cards import CardService
from app.services.repository import CardRepository

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        parser = NativeParser(settings.library_path)
        repository = None if settings.database_url == 'disabled' else CardRepository(settings.database_url)
        application.state.service = CardService(parser, repository)
        yield

    application = FastAPI(title='vCard Parser API', version='1.0.0', lifespan=lifespan,
                          responses={status: {'model': ErrorResponse} for status in (404, 413, 415, 422, 500, 503)})
    application.state.settings = settings
    application.add_middleware(RequestSizeLimit, max_bytes=settings.max_upload_bytes + 65536)
    application.include_router(router)
    static_directory = Path(__file__).parent / 'static'
    application.mount('/static', StaticFiles(directory=static_directory), name='static')

    @application.get('/', include_in_schema=False)
    def interface():
        return FileResponse(static_directory / 'index.html', headers={
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            'X-Content-Type-Options': 'nosniff',
        })

    @application.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Do not echo contact contents or non-JSON exception objects.
        details = [{'location': list(error['loc']), 'message': error['msg'], 'type': error['type']} for error in exc.errors()]
        return JSONResponse({'error': {'code': 'validation_error', 'message': 'Request validation failed.', 'details': details}}, status_code=422)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse({'error': {'code': 'http_error', 'message': str(exc.detail)}}, status_code=exc.status_code)

    @application.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        logger.exception('SQLite operation failed')
        return JSONResponse({'error': {'code': 'database_error', 'message': 'Contact persistence is unavailable.'}}, status_code=503)

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception('Unexpected request failure')
        return JSONResponse({'error': {'code': 'internal_error', 'message': 'An internal error occurred.'}}, status_code=500)

    return application


app = create_app()
