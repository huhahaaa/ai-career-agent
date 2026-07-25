from typing import Generic, Optional, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 0
    message: str = "success"
    data: Optional[DataT] = None


def success_response(
    data: Optional[DataT] = None,
    message: str = "success",
) -> ApiResponse[DataT]:
    return ApiResponse(code=0, message=message, data=data)


class MessageResponse(BaseModel):
    message: str
