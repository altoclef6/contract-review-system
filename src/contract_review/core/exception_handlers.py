from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contract_review.core.exceptions import (
    ContractReviewError,
    UnsupportedDocumentTypeError,
    UnsafeUploadError,
    UploadTooLargeError,
)


ENTERPRISE_API_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/admin",
    "/api/v1/contracts",
    "/api/v1/model-configs",
    "/api/v1/prompt-templates",
    "/api/v1/chats",
    "/api/v1/analysis-history",
    "/api/v1/workflows",
    "/api/v1/notifications",
    "/api/v1/reader",
)


def _is_enterprise_api(request: Request) -> bool:
    return request.url.path.startswith(ENTERPRISE_API_PREFIXES)


def _error_code(status_code: int) -> int:
    return status_code * 100


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": _error_code(status_code), "message": message, "data": None},
    )


async def contract_review_error_handler(
    request: Request,
    exc: ContractReviewError,
) -> JSONResponse:
    _ = request
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, UploadTooLargeError):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, UnsupportedDocumentTypeError):
        status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif isinstance(exc, UnsafeUploadError):
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
