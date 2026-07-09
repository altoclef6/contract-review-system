from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from contract_review.core.exceptions import (
    ContractReviewError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
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

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ContractReviewError, contract_review_error_handler)
