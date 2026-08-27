from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 500


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RateLimitError)
    async def handle_rate_limit(_: Request, exc: RateLimitError) -> JSONResponse:
        logger.warning("openai_rate_limited", exc_info=exc)
        return _upstream_error("AI_RATE_LIMITED", "The AI service is temporarily busy.", 429)

    @app.exception_handler(APITimeoutError)
    async def handle_timeout(_: Request, exc: APITimeoutError) -> JSONResponse:
        logger.warning("openai_timeout", exc_info=exc)
        return _upstream_error("AI_TIMEOUT", "The AI service timed out.", 504)

    @app.exception_handler(APIConnectionError)
    async def handle_connection(_: Request, exc: APIConnectionError) -> JSONResponse:
        logger.error("openai_connection_error", exc_info=exc)
        return _upstream_error("AI_UNAVAILABLE", "The AI service is unavailable.", 503)

    @app.exception_handler(APIStatusError)
    async def handle_status(_: Request, exc: APIStatusError) -> JSONResponse:
        logger.error("openai_api_error", extra={"upstream_status": exc.status_code})
        return _upstream_error("AI_UPSTREAM_ERROR", "The AI service returned an error.", 502)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
            },
        )


def _upstream_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )
