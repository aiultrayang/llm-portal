"""API Proxy Service - Business logic for forwarding requests to LLM services."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.adapters import LMDeployAdapter, LlamaCppAdapter, VLLMAdapter
from app.adapters.base import BaseEngineAdapter
from app.models.service import Service as ServiceModel
from app.models.service import ServiceStatus


@dataclass
class RouteConfig:
    """Route configuration for model-to-service mapping."""

    model_prefix: str  # Model name prefix match (e.g., qwen-*)
    target_service: str  # Target service ID
    api_format: str  # API format: openai / claude / passthrough
    enabled: bool = True
    priority: int = 0  # Higher priority = checked first
    created_at: datetime = field(default_factory=datetime.utcnow)

    def matches(self, model: str) -> bool:
        """Check if this route matches the given model name."""
        if not self.enabled:
            return False
        if self.model_prefix.endswith("*"):
            prefix = self.model_prefix[:-1]
            return model.startswith(prefix)
        return model == self.model_prefix


class ProxyService:
    """API Proxy Service for forwarding requests to LLM services."""

    # Engine adapter registry
    ADAPTERS: Dict[str, type] = {
        "vllm": VLLMAdapter,
        "lmdeploy": LMDeployAdapter,
        "llamacpp": LlamaCppAdapter,
    }

    # Default timeout for requests (seconds)
    DEFAULT_TIMEOUT = 60.0
    STREAM_TIMEOUT = 300.0  # 5 minutes for streaming

    def __init__(self, db: Session):
        """Initialize the proxy service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._routes: List[RouteConfig] = []
        self._default_api_format = "openai"

    def _get_adapter(self, engine: str) -> BaseEngineAdapter:
        """Get the appropriate adapter for an engine.

        Args:
            engine: The engine name (vllm, lmdeploy, llamacpp)

        Returns:
            The corresponding adapter instance

        Raises:
            ValueError: If the engine is not supported
        """
        adapter_class = self.ADAPTERS.get(engine.lower())
        if adapter_class is None:
            raise ValueError(f"Unsupported engine: {engine}")
        return adapter_class()

    def get_route_for_model(self, model: str) -> Optional[RouteConfig]:
        """Find matching route for a model name.

        Args:
            model: The model name to route

        Returns:
            Matching RouteConfig or None
        """
        # Sort routes by priority (descending) and check each
        sorted_routes = sorted(self._routes, key=lambda r: r.priority, reverse=True)
        for route in sorted_routes:
            if route.matches(model):
                return route
        return None

    def get_service_for_model(self, model: str) -> Optional[ServiceModel]:
        """Find running service for a model name.

        Args:
            model: The model name to route

        Returns:
            Service model instance or None
        """
        # First check explicit routes
        route = self.get_route_for_model(model)
        if route:
            service = self.db.query(ServiceModel).filter(
                ServiceModel.id == int(route.target_service),
                ServiceModel.status == ServiceStatus.RUNNING
            ).first()
            if service:
                return service

        # Fall back to finding service by model name pattern
        # Try exact match first
        service = self.db.query(ServiceModel).filter(
            ServiceModel.name == model,
            ServiceModel.status == ServiceStatus.RUNNING
        ).first()

        if service:
            return service

        # Try partial match (service name contains model name or vice versa)
        all_services = self.db.query(ServiceModel).filter(
            ServiceModel.status == ServiceStatus.RUNNING
        ).all()

        for svc in all_services:
            # Check if model name starts with service name or vice versa
            model_lower = model.lower()
            service_name_lower = svc.name.lower()
            if model_lower.startswith(service_name_lower) or service_name_lower.startswith(model_lower):
                return svc

        return None

    async def forward_request(
        self,
        request: Dict[str, Any],
        service_id: str,
        api_type: str = "openai"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Forward request to target service.

        Args:
            request: The request body
            service_id: Target service ID
            api_type: API type (openai / claude / passthrough)

        Yields:
            Response chunks for streaming responses
        """
        service = self.db.query(ServiceModel).filter(ServiceModel.id == int(service_id)).first()
        if not service:
            raise ValueError(f"Service {service_id} not found")

        if service.status != ServiceStatus.RUNNING:
            raise ValueError(f"Service {service_id} is not running")

        if not service.port:
            raise ValueError(f"Service {service_id} has no port assigned")

        # Get adapter for the engine
        adapter = self._get_adapter(service.engine)

        # Transform request
        engine_request = adapter.transform_request(request, api_type)

        # Determine if streaming
        stream = request.get("stream", False)

        # Build URL
        base_url = f"http://localhost:{service.port}"
        endpoint = "/v1/chat/completions"  # Default endpoint

        # Use completions endpoint for non-chat requests
        if "prompt" in request and "messages" not in request:
            endpoint = "/v1/completions"

        url = f"{base_url}{endpoint}"

        if stream:
            # Streaming request
            async for chunk in self.stream_response(request, service, api_type, adapter, url, engine_request):
                yield chunk
        else:
            # Non-streaming request
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.post(url, json=engine_request)
                response.raise_for_status()
                data = response.json()
                transformed = adapter.transform_response(data, api_type)
                yield transformed

    async def stream_response(
        self,
        request: Dict[str, Any],
        service: ServiceModel,
        api_type: str,
        adapter: Optional[BaseEngineAdapter] = None,
        url: Optional[str] = None,
        engine_request: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response from target service.

        Args:
            request: The original request body
            service: Target service model
            api_type: API type (openai / claude / passthrough)
            adapter: Optional pre-fetched adapter
            url: Optional pre-constructed URL
            engine_request: Optional pre-transformed request

        Yields:
            SSE formatted response lines
        """
        if adapter is None:
            adapter = self._get_adapter(service.engine)

        if url is None:
            base_url = f"http://localhost:{service.port}"
            endpoint = "/v1/chat/completions"
            if "prompt" in request and "messages" not in request:
                endpoint = "/v1/completions"
            url = f"{base_url}{endpoint}"

        if engine_request is None:
            engine_request = adapter.transform_request(request, api_type)

        async with httpx.AsyncClient(timeout=self.STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                url,
                json=engine_request,
                timeout=self.STREAM_TIMEOUT
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        try:
                            data = json.loads(data_str)
                            # Transform chunk based on api_type
                            if api_type == "passthrough":
                                transformed = data
                            else:
                                transformed = self._transform_stream_chunk(data, api_type, adapter)
                            yield f"data: {json.dumps(transformed)}\n\n"
                        except json.JSONDecodeError:
                            # Pass through raw data
                            yield f"data: {data_str}\n\n"
                    else:
                        # Non-SSE line, pass through
                        yield f"{line}\n"

    def _transform_stream_chunk(
        self,
        chunk: Dict[str, Any],
        api_type: str,
        adapter: BaseEngineAdapter
    ) -> Dict[str, Any]:
        """Transform a streaming chunk for the target API format.

        Args:
            chunk: The original chunk data
            api_type: Target API type
            adapter: Engine adapter

        Returns:
            Transformed chunk
        """
        if api_type == "openai":
            # Already in OpenAI format
            return chunk

        if api_type == "claude":
            # Transform to Claude streaming format
            return self._convert_chunk_to_claude(chunk)

        # Passthrough
        return chunk

    def _convert_chunk_to_claude(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI streaming chunk to Claude format.

        Args:
            chunk: OpenAI format streaming chunk

        Returns:
            Claude format streaming chunk
        """
        converted = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {}
        }

        if "choices" in chunk and chunk["choices"]:
            choice = chunk["choices"][0]
            delta = choice.get("delta", {})

            # Handle content
            if "content" in delta:
                converted["delta"] = {
                    "type": "text_delta",
                    "text": delta["content"]
                }

            # Handle finish reason
            finish_reason = choice.get("finish_reason")
            if finish_reason:
                converted["type"] = "message_stop"
                converted["delta"] = {}

        return converted

    # Route management methods

    def add_route(
        self,
        model_prefix: str,
        target_service: str,
        api_format: str = "openai",
        priority: int = 0
    ) -> RouteConfig:
        """Add a new route configuration.

        Args:
            model_prefix: Model name prefix pattern
            target_service: Target service ID
            api_format: API format (openai/claude/passthrough)
            priority: Route priority

        Returns:
            Created RouteConfig
        """
        route = RouteConfig(
            model_prefix=model_prefix,
            target_service=target_service,
            api_format=api_format,
            priority=priority
        )
        self._routes.append(route)
        return route

    def remove_route(self, model_prefix: str) -> bool:
        """Remove a route by model prefix.

        Args:
            model_prefix: Model prefix to remove

        Returns:
            True if removed, False if not found
        """
        for i, route in enumerate(self._routes):
            if route.model_prefix == model_prefix:
                self._routes.pop(i)
                return True
        return False

    def get_routes(self) -> List[RouteConfig]:
        """Get all route configurations.

        Returns:
            List of RouteConfig
        """
        return sorted(self._routes, key=lambda r: r.priority, reverse=True)

    def clear_routes(self) -> None:
        """Clear all route configurations."""
        self._routes.clear()

    def set_routes(self, routes: List[Dict[str, Any]]) -> List[RouteConfig]:
        """Set routes from configuration.

        Args:
            routes: List of route configurations

        Returns:
            List of created RouteConfig
        """
        self.clear_routes()
        created = []
        for route_data in routes:
            route = self.add_route(
                model_prefix=route_data.get("model_prefix", "*"),
                target_service=str(route_data.get("target_service", "")),
                api_format=route_data.get("api_format", "openai"),
                priority=route_data.get("priority", 0)
            )
            created.append(route)
        return created

    # Model listing methods

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from running services.

        Returns:
            List of model information dictionaries
        """
        models = []

        # Get all running services
        services = self.db.query(ServiceModel).filter(
            ServiceModel.status == ServiceStatus.RUNNING
        ).all()

        for service in services:
            # Create model entry from service
            model_info = {
                "id": service.name,
                "object": "model",
                "created": int(service.created_at.timestamp()) if service.created_at else 0,
                "owned_by": "local-llm-platform",
                "service_id": service.id,
                "engine": service.engine,
                "port": service.port
            }
            models.append(model_info)

        # Add models from routes
        for route in self._routes:
            if not route.enabled:
                continue
            # Check if target service is running
            try:
                service = self.db.query(ServiceModel).filter(
                    ServiceModel.id == int(route.target_service),
                    ServiceModel.status == ServiceStatus.RUNNING
                ).first()
                if service:
                    model_info = {
                        "id": route.model_prefix.rstrip("*"),
                        "object": "model",
                        "created": int(route.created_at.timestamp()),
                        "owned_by": "local-llm-platform",
                        "service_id": service.id,
                        "engine": service.engine,
                        "port": service.port,
                        "api_format": route.api_format
                    }
                    models.append(model_info)
            except (ValueError, TypeError):
                pass

        return models

    # Request building helpers

    def build_openai_chat_request(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Build an OpenAI-format chat completion request.

        Args:
            model: Model name
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream
            **kwargs: Additional parameters

        Returns:
            Request dictionary
        """
        request = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }

        if max_tokens:
            request["max_tokens"] = max_tokens

        # Add additional parameters
        for key, value in kwargs.items():
            if value is not None:
                request[key] = value

        return request

    def build_openai_completion_request(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 16,
        temperature: float = 1.0,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Build an OpenAI-format text completion request.

        Args:
            model: Model name
            prompt: Text prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream
            **kwargs: Additional parameters

        Returns:
            Request dictionary
        """
        request = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream
        }

        # Add additional parameters
        for key, value in kwargs.items():
            if value is not None:
                request[key] = value

        return request

    def build_claude_request(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: float = 1.0,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Build a Claude-format message request.

        Args:
            model: Model name
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            system: System prompt
            temperature: Sampling temperature
            stream: Whether to stream
            **kwargs: Additional parameters

        Returns:
            Request dictionary
        """
        request = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream
        }

        if system:
            request["system"] = system

        # Add additional parameters
        for key, value in kwargs.items():
            if value is not None:
                request[key] = value

        return request

    # Response formatting helpers

    def format_openai_response(
        self,
        content: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        finish_reason: str = "stop"
    ) -> Dict[str, Any]:
        """Format a response in OpenAI format.

        Args:
            content: Generated content
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            finish_reason: Completion reason

        Returns:
            OpenAI-format response
        """
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(datetime.utcnow().timestamp()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

    def format_claude_response(
        self,
        content: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        stop_reason: str = "end_turn"
    ) -> Dict[str, Any]:
        """Format a response in Claude format.

        Args:
            content: Generated content
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            stop_reason: Stop reason

        Returns:
            Claude-format response
        """
        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [
                {
                    "type": "text",
                    "text": content
                }
            ],
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        }
