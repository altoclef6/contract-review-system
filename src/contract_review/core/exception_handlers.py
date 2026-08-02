from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contract_review.core.exceptions import (
    ContractReviewError,
    DocumentTextExtractionError,
    UnsafeUploadError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)

logger = logging.getLogger(__name__)


def _is_enterprise_api(request: Request) -> bool:
    return request.url.path.startswith("/api/v1/")


def _error_code(status_code: int) -> int:
    return status_code * 100


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": _error_code(status_code),
            "message": message,
            "detail": message,
            "data": None,
        },
    )


async def contract_review_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    _ = request
    if not isinstance(exc, ContractReviewError):
        raise exc
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, UploadTooLargeError):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, UnsupportedDocumentTypeError):
        status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif isinstance(exc, UnsafeUploadError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, DocumentTextExtractionError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ContractReviewError, contract_review_error_handler)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_enterprise_api(request):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        message = str(exc.detail) if exc.detail else "请求处理失败"
        return _error_response(exc.status_code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if not _is_enterprise_api(request):
            return JSONResponse(status_code=422, content={"detail": exc.errors()})
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "请求参数校验失败")

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request error method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        if not _is_enterprise_api(request):
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "系统暂时无法处理该请求，请稍后重试。"},
            )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "系统暂时无法处理该请求，请稍后重试；如持续失败请联系管理员。",
        )
