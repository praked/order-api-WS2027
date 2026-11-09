"""House error format: {"error": "<code>"} plus an HTTP status. See the add-endpoint skill."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(HTTPException):
    """Raise APIError(404, "order_not_found") instead of returning ad-hoc JSON."""

    def __init__(self, status_code: int, code: str, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=code, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
