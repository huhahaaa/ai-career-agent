from typing import Any, Dict, Optional


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data
        self.headers = headers
