from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 0
    message: str = "success"
    data: DataT


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None


class MessageData(BaseModel):
    message: str


def api_success(data: DataT, message: str = "success") -> ApiResponse[DataT]:
    return ApiResponse[DataT](code=0, message=message, data=data)
