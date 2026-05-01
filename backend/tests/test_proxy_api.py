"""Tests for API Proxy functionality."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.service import Service as ServiceModel
from app.models.service import ServiceStatus
from app.schemas.service import ServiceCreate
from app.services.proxy_service import ProxyService, RouteConfig


# Test database setup
@pytest.fixture
def db_session() -> Session:
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def proxy_service(db_session: Session) -> ProxyService:
    """Create a proxy service instance."""
    return ProxyService(db_session)


@pytest.fixture
def sample_service(db_session: Session) -> ServiceModel:
    """Create a sample running service."""
    service = ServiceModel(
        id=1,
        name="test-qwen-model",
        engine="vllm",
        config='{"model": "Qwen/Qwen2.5-7B-Instruct"}',
        status=ServiceStatus.RUNNING,
        port=8000,
        pid=12345,
        created_at=datetime.utcnow()
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


class TestProxyServiceInit:
    """Tests for ProxyService initialization."""

    def test_init(self, proxy_service: ProxyService) -> None:
        """Test proxy service initialization."""
        assert proxy_service is not None
        assert proxy_service._routes == []
        assert proxy_service._default_api_format == "openai"


class TestRouteManagement:
    """Tests for route management."""

    def test_add_route(self, proxy_service: ProxyService) -> None:
        """Test adding a route."""
        route = proxy_service.add_route(
            model_prefix="qwen-*",
            target_service="1",
            api_format="openai",
            priority=10
        )
        assert route.model_prefix == "qwen-*"
        assert route.target_service == "1"
        assert route.api_format == "openai"
        assert route.priority == 10
        assert route.enabled is True

    def test_remove_route(self, proxy_service: ProxyService) -> None:
        """Test removing a route."""
        proxy_service.add_route("qwen-*", "1", "openai")
        result = proxy_service.remove_route("qwen-*")
        assert result is True
        assert len(proxy_service._routes) == 0

    def test_remove_route_not_found(self, proxy_service: ProxyService) -> None:
        """Test removing a non-existent route."""
        result = proxy_service.remove_route("nonexistent-*")
        assert result is False

    def test_get_routes_sorted_by_priority(self, proxy_service: ProxyService) -> None:
        """Test getting routes sorted by priority."""
        proxy_service.add_route("model-a-*", "1", "openai", priority=5)
        proxy_service.add_route("model-b-*", "2", "claude", priority=10)
        routes = proxy_service.get_routes()
        assert len(routes) == 2
        assert routes[0].priority == 10  # Higher priority first
        assert routes[1].priority == 5

    def test_set_routes_bulk(self, proxy_service: ProxyService) -> None:
        """Test bulk setting routes."""
        routes_data = [
            {"model_prefix": "model-a-*", "target_service": "1", "api_format": "openai"},
            {"model_prefix": "model-b-*", "target_service": "2", "api_format": "claude"}
        ]
        proxy_service.set_routes(routes_data)
        assert len(proxy_service._routes) == 2

    def test_clear_routes(self, proxy_service: ProxyService) -> None:
        """Test clearing all routes."""
        proxy_service.add_route("test-*", "1", "openai")
        proxy_service.clear_routes()
        assert len(proxy_service._routes) == 0


class TestRouteMatching:
    """Tests for route matching logic."""

    def test_route_matches_wildcard(self) -> None:
        """Test wildcard matching."""
        route = RouteConfig(
            model_prefix="qwen-*",
            target_service="1",
            api_format="openai"
        )
        assert route.matches("qwen-7b") is True
        assert route.matches("qwen-72b") is True
        assert route.matches("llama-7b") is False

    def test_route_matches_exact(self) -> None:
        """Test exact matching."""
        route = RouteConfig(
            model_prefix="exact-model",
            target_service="1",
            api_format="openai"
        )
        assert route.matches("exact-model") is True
        assert route.matches("exact-model-v2") is False

    def test_route_matches_disabled(self) -> None:
        """Test disabled route doesn't match."""
        route = RouteConfig(
            model_prefix="test-*",
            target_service="1",
            api_format="openai"
        )
        route.enabled = False
        assert route.matches("test-model") is False

    def test_get_route_for_model_wildcard(self, proxy_service: ProxyService) -> None:
        """Test finding route for model with wildcard."""
        proxy_service.add_route("qwen-*", "1", "openai", priority=5)
        proxy_service.add_route("llama-*", "2", "openai", priority=10)

        route = proxy_service.get_route_for_model("llama-7b")
        assert route is not None
        assert route.model_prefix == "llama-*"

        route = proxy_service.get_route_for_model("qwen-7b")
        assert route is not None
        assert route.model_prefix == "qwen-*"

    def test_get_route_for_model_not_found(self, proxy_service: ProxyService) -> None:
        """Test when no route found."""
        route = proxy_service.get_route_for_model("unknown-model")
        assert route is None


class TestServiceLookup:
    """Tests for service lookup."""

    def test_get_service_for_model_by_route(
        self, proxy_service: ProxyService, sample_service: ServiceModel
    ) -> None:
        """Test finding service through route."""
        proxy_service.add_route("test-*", "1", "openai")
        service = proxy_service.get_service_for_model("test-model")
        assert service is not None
        assert service.id == 1

    def test_get_service_for_model_by_name(
        self, proxy_service: ProxyService, sample_service: ServiceModel
    ) -> None:
        """Test finding service by name match."""
        # Exact match
        service = proxy_service.get_service_for_model("test-qwen-model")
        assert service is not None

        # Partial match
        service = proxy_service.get_service_for_model("test-qwen")
        assert service is not None

    def test_get_service_for_model_not_found(self, proxy_service: ProxyService) -> None:
        """Test when no service found."""
        service = proxy_service.get_service_for_model("nonexistent")
        assert service is None

    def test_get_service_for_model_stopped_service(
        self, proxy_service: ProxyService, db_session: Session
    ) -> None:
        """Test that stopped services are not matched."""
        service = ServiceModel(
            id=2,
            name="stopped-service",
            engine="vllm",
            status=ServiceStatus.STOPPED,
            created_at=datetime.utcnow()
        )
        db_session.add(service)
        db_session.commit()

        result = proxy_service.get_service_for_model("stopped-service")
        assert result is None


class TestModelListing:
    """Tests for model listing."""

    def test_get_available_models(
        self, proxy_service: ProxyService, sample_service: ServiceModel
    ) -> None:
        """Test getting available models list."""
        models = proxy_service.get_available_models()
        assert len(models) == 1
        assert models[0]["id"] == "test-qwen-model"
        assert models[0]["object"] == "model"
        assert models[0]["engine"] == "vllm"

    def test_get_available_models_empty(self, proxy_service: ProxyService) -> None:
        """Test listing models when none running."""
        models = proxy_service.get_available_models()
        assert len(models) == 0

    def test_get_available_models_with_routes(
        self, proxy_service: ProxyService, sample_service: ServiceModel
    ) -> None:
        """Test getting models from routes."""
        proxy_service.add_route("custom-*", "1", "openai")
        models = proxy_service.get_available_models()
        model_ids = [m["id"] for m in models]
        assert "test-qwen-model" in model_ids
        assert "custom-" in model_ids


class TestRequestBuilding:
    """Tests for request building."""

    def test_build_openai_chat_request(self, proxy_service: ProxyService) -> None:
        """Test building OpenAI chat request."""
        request = proxy_service.build_openai_chat_request(
            model="qwen-7b",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=100,
            stream=True
        )
        assert request["model"] == "qwen-7b"
        assert request["messages"] == [{"role": "user", "content": "Hello"}]
        assert request["temperature"] == 0.7
        assert request["max_tokens"] == 100
        assert request["stream"] is True

    def test_build_openai_completion_request(self, proxy_service: ProxyService) -> None:
        """Test building OpenAI completion request."""
        request = proxy_service.build_openai_completion_request(
            model="llama-7b",
            prompt="Hello, world",
            max_tokens=50,
            temperature=0.5
        )
        assert request["model"] == "llama-7b"
        assert request["prompt"] == "Hello, world"
        assert request["max_tokens"] == 50
        assert request["temperature"] == 0.5

    def test_build_claude_request(self, proxy_service: ProxyService) -> None:
        """Test building Claude request."""
        request = proxy_service.build_claude_request(
            model="claude-3",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
            system="You are helpful.",
            temperature=0.8
        )
        assert request["model"] == "claude-3"
        assert request["messages"] == [{"role": "user", "content": "Hello"}]
        assert request["system"] == "You are helpful."
        assert request["max_tokens"] == 1024


class TestResponseFormatting:
    """Tests for response formatting."""

    def test_format_openai_response(self, proxy_service: ProxyService) -> None:
        """Test formatting OpenAI response."""
        response = proxy_service.format_openai_response(
            content="Hello, world!",
            model="qwen-7b",
            prompt_tokens=10,
            completion_tokens=20,
            finish_reason="stop"
        )
        assert response["model"] == "qwen-7b"
        assert response["choices"][0]["message"]["content"] == "Hello, world!"
        assert response["usage"]["prompt_tokens"] == 10
        assert response["usage"]["completion_tokens"] == 20

    def test_format_claude_response(self, proxy_service: ProxyService) -> None:
        """Test formatting Claude response."""
        response = proxy_service.format_claude_response(
            content="Hello!",
            model="claude-3",
            input_tokens=10,
            output_tokens=5
        )
        assert response["model"] == "claude-3"
        assert response["content"][0]["type"] == "text"
        assert response["content"][0]["text"] == "Hello!"
        assert response["usage"]["input_tokens"] == 10


class TestErrorHandling:
    """Tests for error handling."""

    def test_get_adapter_unsupported_engine(self, proxy_service: ProxyService) -> None:
        """Test getting adapter for unsupported engine."""
        with pytest.raises(ValueError, match="Unsupported engine"):
            proxy_service._get_adapter("unsupported_engine")

    def test_forward_request_service_not_found(self, proxy_service: ProxyService) -> None:
        """Test forwarding to non-existent service."""
        with pytest.raises(ValueError, match="Service 999 not found"):
            import asyncio
            asyncio.run(proxy_service.forward_request(
                {"model": "test", "messages": []},
                "999"
            ).__anext__())

    def test_forward_request_service_not_running(
        self, proxy_service: ProxyService, db_session: Session
    ) -> None:
        """Test forwarding to stopped service."""
        service = ServiceModel(
            id=2,
            name="stopped-service",
            engine="vllm",
            status=ServiceStatus.STOPPED,
            created_at=datetime.utcnow()
        )
        db_session.add(service)
        db_session.commit()

        with pytest.raises(ValueError, match="Service 2 is not running"):
            import asyncio
            asyncio.run(proxy_service.forward_request(
                {"model": "stopped-service", "messages": []},
                "2"
            ).__anext__())

    def test_forward_request_service_no_port(
        self, proxy_service: ProxyService, db_session: Session
    ) -> None:
        """Test forwarding to service without port."""
        service = ServiceModel(
            id=3,
            name="no-port-service",
            engine="vllm",
            status=ServiceStatus.RUNNING,
            port=None,
            created_at=datetime.utcnow()
        )
        db_session.add(service)
        db_session.commit()

        with pytest.raises(ValueError, match="Service 3 has no port"):
            import asyncio
            asyncio.run(proxy_service.forward_request(
                {"model": "no-port-service", "messages": []},
                "3"
            ).__anext__())


class TestAPIFormatConversions:
    """Tests for API format conversion."""

    def test_convert_chunk_to_claude(self, proxy_service: ProxyService) -> None:
        """Test converting OpenAI chunk to Claude format."""
        chunk = {
            "choices": [{
                "delta": {"content": "Hello"},
                "finish_reason": None
            }]
        }

        converted = proxy_service._convert_chunk_to_claude(chunk)

        assert converted["type"] == "content_block_delta"
        assert converted["delta"]["type"] == "text_delta"
        assert converted["delta"]["text"] == "Hello"

    def test_convert_chunk_to_claude_stop(self, proxy_service: ProxyService) -> None:
        """Test converting chunk with finish reason."""
        chunk = {
            "choices": [{
                "delta": {},
                "finish_reason": "stop"
            }]
        }

        converted = proxy_service._convert_chunk_to_claude(chunk)
        assert converted["type"] == "message_stop"


class TestStreaming:
    """Tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_forward_request_non_stream(
        self, proxy_service: ProxyService, sample_service: ServiceModel
    ) -> None:
        """Test non-streaming request forwarding."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            results = []
            async for chunk in proxy_service.forward_request(
                {"model": "test-qwen-model", "messages": [], "stream": False},
                "1",
                "openai"
            ):
                results.append(chunk)

            assert len(results) == 1
            assert results[0]["model"] == "test-model"


class TestRouteConfigDataclass:
    """Tests for RouteConfig dataclass."""

    def test_route_config_creation(self) -> None:
        """Test creating a RouteConfig."""
        route = RouteConfig(
            model_prefix="test-*",
            target_service="1",
            api_format="openai",
            enabled=True,
            priority=5
        )
        assert route.model_prefix == "test-*"
        assert route.target_service == "1"
        assert route.api_format == "openai"
        assert route.enabled is True
        assert route.priority == 5

    def test_route_config_default_values(self) -> None:
        """Test RouteConfig default values."""
        route = RouteConfig(
            model_prefix="test-*",
            target_service="1",
            api_format="openai"
        )
        assert route.enabled is True
        assert route.priority == 0

    def test_route_config_matches_prefix(self) -> None:
        """Test RouteConfig matches with prefix pattern."""
        route = RouteConfig(
            model_prefix="llama-*",
            target_service="2",
            api_format="openai"
        )
        assert route.matches("llama-7b") is True
        assert route.matches("llama-13b") is True
        assert route.matches("qwen-7b") is False
