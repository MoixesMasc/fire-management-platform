"""Fire Validation Microservice — FastAPI entry point (EC2/Docker)."""
import os

from fastapi import FastAPI

from shared.fastapi_utils import add_health_route, register_error_handlers
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
register_error_handlers(app)
add_health_route(app, "fire_validation")
