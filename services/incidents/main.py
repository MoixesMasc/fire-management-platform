"""Incidents Microservice — FastAPI entry point (AWS Lambda via Mangum)."""
import os

from fastapi import FastAPI

from shared.fastapi_utils import add_health_route, register_error_handlers
from shared.logging_config import get_logger, setup_logging
from services.incidents.router import router

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = FastAPI(
    title="Fire Platform — Incidents Service",
    description="CRUD for fire incident reports backed by DynamoDB",
    version="1.0.0",
)

app.include_router(router)
register_error_handlers(app)
add_health_route(app, "incidents")

# ── Lambda handler (Mangum) ────────────────────────────────────────────────────
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None
