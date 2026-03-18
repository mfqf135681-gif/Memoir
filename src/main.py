"""FastAPI application entry point for Memoir."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import chat, config, files, import as import_routes, logs, memories
from .core.config import get_settings
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger("memoir")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    logger.info(f"Starting Memoir - Data directory: {settings.storage.base_dir}")

    # Ensure data directory exists
    data_dir = Path(settings.storage.base_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info("Shutting down Memoir")


# Create FastAPI app
app = FastAPI(
    title="Memoir",
    description="AI Long-term Memory Framework - File-based memory with transparency and associative retrieval",
    version="0.1.0",
    lifespan=lifespan,
    # Increase upload limit to 50MB
    docs_url=None,
    redoc_url=None,
)

# Increase default upload limit to 50MB
app.state.upload_max_size = 50 * 1024 * 1024

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(memories.router)
app.include_router(files.router)
app.include_router(config.router)
app.include_router(logs.router)
app.include_router(import_routes.router)

# Static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Root endpoint - serve WebUI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": "Memoir",
        "version": "0.1.0",
        "description": "AI Long-term Memory Framework",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )
