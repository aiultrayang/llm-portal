"""FastAPI application entry point for the local LLM deployment platform."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.benchmark import router as benchmark_router
from app.api.logs import router as logs_router
from app.api.models import router as models_router
from app.api.proxy import router as proxy_router, config_router as proxy_config_router
from app.api.services import router as services_router
from app.api.system import router as system_router
from app.api.system_config import router as config_router
from app.config import (
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CORS_ORIGINS,
)
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # 启动时初始化数据库
    init_db()
    yield
    # 关闭时清理资源（如需要）


# Create FastAPI application
app = FastAPI(
    title="Local LLM Deployment Platform",
    description="A platform for deploying and managing local large language models",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# Register API routers
app.include_router(models_router)
app.include_router(services_router)
app.include_router(proxy_router)
app.include_router(proxy_config_router)
app.include_router(logs_router)
app.include_router(benchmark_router)
app.include_router(system_router)
app.include_router(config_router)


@app.get("/")
async def root() -> dict:
    """Root endpoint returning API information."""
    return {
        "message": "Local LLM Deployment Platform API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": "local-llm-platform",
    }


if __name__ == "__main__":
    import uvicorn
    from app.config import API_HOST, API_PORT, API_RELOAD

    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD,
    )
