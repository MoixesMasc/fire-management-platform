"""Helpers de FastAPI compartidos entre microservicios."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.logging_config import get_logger

logger = get_logger(__name__)


def serializable_errors(exc: RequestValidationError) -> list:
    """
    Convierte los errores de validación de Pydantic v2 a una lista JSON-serializable.
    El campo 'ctx' puede contener objetos Python no serializables (ej: ValueError);
    se convierten a string para evitar TypeError en JSONResponse.
    """
    errors = []
    for error in exc.errors():
        entry = dict(error)
        if "ctx" in entry:
            entry["ctx"] = {k: str(v) for k, v in entry["ctx"].items()}
        entry.pop("url", None)
        errors.append(entry)
    return errors


def register_error_handlers(app: FastAPI) -> None:
    """Registra los handlers globales de error 422 y 500 en una app FastAPI."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = serializable_errors(exc)
        logger.warning("validation_error", errors=errors, path=str(request.url))
        return JSONResponse(
            status_code=422,
            content={"detail": errors, "error_code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), path=str(request.url), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )


def add_health_route(app: FastAPI, service_name: str) -> None:
    """Agrega el endpoint GET /health a la app."""

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}
