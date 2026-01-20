"""FastAPI application for Certificate Validation Agent.
# Reload triggered for ENV Update (Expiration Days)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from loguru import logger

from app.config.settings import settings
from app.config.database import init_db, close_db
from app.config.logging import setup_logging
from app.api import processing, files, requests, certificates

# Set GCP Credentials explicitly for Vertex AI and Storage
import os
if settings.gcp_service_account_key_path:
    key_path = os.path.abspath(settings.gcp_service_account_key_path)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
    logger.info(f"Set GCP Credentials path: {key_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging()
    logger.info("Starting Certificate Validation Agent API")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
        logger.info("App will run without database (limited functionality)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Database cleanup skipped: {e}")


# Create FastAPI app
app = FastAPI(
    title="Certificate Validation Agent",
    description="AI-powered certificate validation system with OCR and document analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers
app.include_router(processing.router)
app.include_router(files.router)
app.include_router(requests.router)
app.include_router(certificates.router)

# Serve static files for local dev mode
from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory="static/uploads"), name="static")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Certificate Validation Agent",
        "version": "1.0.0"
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            },
            "data": None
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
        log_level=settings.log_level.lower(),
    )
