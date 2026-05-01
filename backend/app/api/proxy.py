"""API Proxy Routes - Forward requests to LLM services."""

import json
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.service import Service as ServiceModel
from app.models.service import ServiceStatus
from app.services.proxy_service import ProxyService, RouteConfig


# Pydantic schemas for request/response

class ChatMessage(BaseModel):
    """Chat message schema."""

    role: str = Field(..., description="Message role: system/user/assistant")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """OpenAI-format chat completion request."""

    model: str = Field(..., description="Model name")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum tokens")
    stream: bool = Field(default=False, description="Stream response")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: Optional[int] = Field(default=None, ge=-1, description="Top-k sampling")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)

    model_config = {"protected_namespaces": ()}


class CompletionRequest(BaseModel):
    """OpenAI-format text completion request."""

    model: str = Field(..., description="Model name")
    prompt: str = Field(..., description="Text prompt")
    max_tokens: int = Field(default=16, ge=1, description="Maximum tokens")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    stream: bool = Field(default=False, description="Stream response")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=-1)
    stop: Optional[List[str]] = Field(default=None)

    model_config = {"protected_namespaces": ()}


class ClaudeMessage(BaseModel):
    """Claude-format message."""

    role: str = Field(..., description="Message role")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="Message content")


class ClaudeMessageRequest(BaseModel):
    """Claude-format message request."""

    model: str = Field(..., description="Model name")
    messages: List[ClaudeMessage] = Field(..., description="Messages")
    max_tokens: int = Field(default=1024, ge=1, description="Maximum tokens")
    system: Optional[str] = Field(default=None, description="System prompt")
    temperature: float = Field(default=1.0, ge=0.0, le=1.0)
    stream: bool = Field(default=False, description="Stream response")
    top_p: Optional[float] = Field(default=None)
    top_k: Optional[int] = Field(default=None)
    stop_sequences: Optional[List[str]] = Field(default=None)

    model_config = {"protected_namespaces": ()}


class RouteCreate(BaseModel):
    """Route creation schema."""

    model_prefix: str = Field(..., description="Model name prefix pattern")
    target_service: str = Field(..., description="Target service ID")
    api_format: str = Field(default="openai", description="API format")
    priority: int = Field(default=0, description="Route priority")


class ConfigUpdate(BaseModel):
    """Proxy configuration update."""

    default_api_format: Optional[str] = Field(default=None, description="Default API format")
    routes: Optional[List[RouteCreate]] = Field(default=None, description="Route configurations")


class ModelResponse(BaseModel):
    """Model response schema."""

    id: str
    object: str = "model"
    created: int
    owned_by: str
    service_id: Optional[int] = None
    engine: Optional[str] = None
    port: Optional[int] = None


class ModelsListResponse(BaseModel):
    """Models list response."""

    object: str = "list"
    data: List[ModelResponse]


# Router
router = APIRouter(prefix="/v1", tags=["proxy"])


def get_proxy_service(db: Session = Depends(get_db)) -> ProxyService:
    """Get proxy service instance."""
    return ProxyService(db)


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """OpenAI-format chat completion endpoint.

    Forwards requests to the appropriate LLM service based on model routing.
    """
    # Convert to dict
    request_dict = request.model_dump()

    # Find service for model
    service = proxy.get_service_for_model(request.model)
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"No running service found for model: {request.model}"
        )

    # Check if streaming
    if request.stream:
        return StreamingResponse(
            proxy.forward_request(request_dict, str(service.id), "openai"),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming response
        result = None
        async for chunk in proxy.forward_request(request_dict, str(service.id), "openai"):
            result = chunk
        return result


@router.post("/completions")
async def completions(
    request: CompletionRequest,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """OpenAI-format text completion endpoint."""
    request_dict = request.model_dump()

    # Find service for model
    service = proxy.get_service_for_model(request.model)
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"No running service found for model: {request.model}"
        )

    if request.stream:
        return StreamingResponse(
            proxy.forward_request(request_dict, str(service.id), "openai"),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        result = None
        async for chunk in proxy.forward_request(request_dict, str(service.id), "openai"):
            result = chunk
        return result


@router.post("/messages")
async def messages(
    request: ClaudeMessageRequest,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """Claude-format message endpoint."""
    request_dict = request.model_dump()

    # Find service for model
    service = proxy.get_service_for_model(request.model)
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"No running service found for model: {request.model}"
        )

    if request.stream:
        # For Claude streaming, we need to handle SSE differently
        async def stream_claude():
            async for chunk in proxy.stream_response(
                request_dict, service, "claude"
            ):
                yield chunk

        return StreamingResponse(
            stream_claude(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        result = None
        async for chunk in proxy.forward_request(request_dict, str(service.id), "claude"):
            result = chunk
        return result


@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    proxy: ProxyService = Depends(get_proxy_service)
):
    """List available models from running services."""
    models = proxy.get_available_models()
    model_responses = [
        ModelResponse(**model) for model in models
    ]
    return ModelsListResponse(
        object="list",
        data=model_responses
    )


# Proxy configuration endpoints (under /api/proxy)

config_router = APIRouter(prefix="/api/proxy", tags=["proxy-config"])


@config_router.post("/config")
async def set_proxy_config(
    config: ConfigUpdate,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """Set proxy configuration."""
    if config.default_api_format:
        proxy._default_api_format = config.default_api_format

    if config.routes is not None:
        proxy.set_routes([r.model_dump() for r in config.routes])

    return {
        "status": "success",
        "default_api_format": proxy._default_api_format,
        "routes_count": len(proxy._routes)
    }


@config_router.get("/routes")
async def get_routes(
    proxy: ProxyService = Depends(get_proxy_service)
):
    """Get current route configurations."""
    routes = proxy.get_routes()
    return {
        "routes": [
            {
                "model_prefix": r.model_prefix,
                "target_service": r.target_service,
                "api_format": r.api_format,
                "enabled": r.enabled,
                "priority": r.priority,
                "created_at": r.created_at.isoformat()
            }
            for r in routes
        ]
    }


@config_router.post("/routes")
async def add_route(
    route: RouteCreate,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """Add a new route configuration."""
    # Validate target service exists
    db = proxy.db
    service = db.query(ServiceModel).filter(
        ServiceModel.id == int(route.target_service)
    ).first()

    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service {route.target_service} not found"
        )

    # Validate api_format
    valid_formats = ["openai", "claude", "passthrough"]
    if route.api_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid api_format. Must be one of: {valid_formats}"
        )

    created_route = proxy.add_route(
        model_prefix=route.model_prefix,
        target_service=route.target_service,
        api_format=route.api_format,
        priority=route.priority
    )

    return {
        "status": "success",
        "route": {
            "model_prefix": created_route.model_prefix,
            "target_service": created_route.target_service,
            "api_format": created_route.api_format,
            "priority": created_route.priority,
            "enabled": created_route.enabled
        }
    }


@config_router.delete("/routes/{model_prefix:path}")
async def delete_route(
    model_prefix: str,
    proxy: ProxyService = Depends(get_proxy_service)
):
    """Delete a route by model prefix."""
    # URL decode the model_prefix if needed
    import urllib.parse
    decoded_prefix = urllib.parse.unquote(model_prefix)

    removed = proxy.remove_route(decoded_prefix)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Route with prefix '{decoded_prefix}' not found"
        )

    return {
        "status": "success",
        "message": f"Route '{decoded_prefix}' removed"
    }


# Health check for proxy
@config_router.get("/health")
async def proxy_health():
    """Proxy service health check."""
    return {
        "status": "healthy",
        "service": "api-proxy"
    }
