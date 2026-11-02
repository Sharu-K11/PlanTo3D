import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from app.config import Settings, get_settings
from app.docs_page import DOCS_UNAVAILABLE_HTML
from app.routers import health, segmentation

API_V1_PREFIX = "/api/v1"

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def load_segmentation_service(config: Settings) -> Any | None:
    """Load the model if enabled and available; otherwise /segment answers 503."""
    if not config.segmentation_enabled:
        logger.info("Segmentation disabled (SEGMENTATION_ENABLED=false)")
        return None
    if not config.segmentation_model_path.is_file():
        logger.warning("Segmentation weights not found at %s", config.segmentation_model_path)
        return None
    try:
        # Imported lazily: torch/smp come from requirements-ml.txt and are absent in Docker/CI.
        from app.services.segmentation_service import SegmentationService
    except ImportError as error:
        logger.warning("Segmentation unavailable, ML packages not installed: %s", error)
        return None
    try:
        service = await asyncio.to_thread(SegmentationService, config.segmentation_model_path)
    except Exception:
        logger.exception("Failed to load segmentation model")
        return None
    logger.info("Segmentation model loaded successfully on %s", service.device)
    return service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.segmentation_service = await load_segmentation_service(settings)
    yield
    app.state.segmentation_service = None


# Swagger UI and ReDoc are replaced by Scalar at /docs.
app = FastAPI(
    title="Plan2World API",
    version="0.0.4-beta",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

for router in (health.router, segmentation.router):
    app.include_router(router, prefix=API_V1_PREFIX)


@app.get("/docs", include_in_schema=False)
async def scalar_docs() -> HTMLResponse:
    if not settings.dev:
        return HTMLResponse(DOCS_UNAVAILABLE_HTML, headers={"Cache-Control": "no-store"})
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=f"{app.title} docs")
