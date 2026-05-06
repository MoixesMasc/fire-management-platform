"""Fire Validation Microservice — FastAPI entry point (EC2/Docker)."""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _serializable_errors(exc: RequestValidationError) -> list:
    errors = []
    for error in exc.errors():
        entry = dict(error)
        if "ctx" in entry:
            entry["ctx"] = {k: str(v) for k, v in entry["ctx"].items()}
        entry.pop("url", None)
        errors.append(entry)
    return errors

from shared.logging_config import get_logger, setup_logging
from services.fire_validation.router import router

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = FastAPI(
    title="Fire Platform — Fire Validation Service",
    description="Validates fire incidents using AWS Rekognition image analysis",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = _serializable_errors(exc)
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


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fire_validation"}
