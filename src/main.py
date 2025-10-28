# --------------------------------------------------------------------------
# Main server application module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.api import api_router
from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print("Starting Auth Server")

    # Initialize database
    from src.core.database import init_db

    await init_db()

    print("Auth Server started successfully")

    yield

    # Shutdown
    print("Shutting down Auth Server")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Auth Server",
        description="Authentication service for bnbong.xyz",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # Add routes
    app.include_router(api_router)

    # Initialize Prometheus metrics
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy", "service": "auth-server"}

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        return {
            "message": "Welcome to Auth Server",
            "version": "1.0.0",
            "docs": "/docs" if settings.ENVIRONMENT != "production" else None,
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
