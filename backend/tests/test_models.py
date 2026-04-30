"""Unit tests for database models."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import (
    Model,
    Service,
    ServiceStatus,
    BenchmarkResult,
    BenchmarkStatus,
    RequestLog,
    ResponseLog,
)


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory SQLite database for testing.

    Yields:
        Session: A SQLAlchemy session connected to the test database.
    """
    # Use in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestModel:
    """Tests for the Model class."""

    def test_create_model(self, db_session: Session) -> None:
        """Test creating a Model record."""
        model = Model(
            name="LLaMA-2-7B",
            path="/models/llama-2-7b",
            size=14000000000,
            format="gguf",
            supported_engines=["llama.cpp", "vllm"],
            metadata_json={"quantization": "Q4_K_M", "context_length": 4096},
        )

        db_session.add(model)
        db_session.commit()

        assert model.id is not None
        assert model.name == "LLaMA-2-7B"
        assert model.path == "/models/llama-2-7b"
        assert model.size == 14000000000
        assert model.format == "gguf"
        assert model.supported_engines == ["llama.cpp", "vllm"]
        assert model.metadata_json["quantization"] == "Q4_K_M"
        assert model.created_at is not None

    def test_model_to_dict(self, db_session: Session) -> None:
        """Test Model to_dict method."""
        model = Model(
            name="Mistral-7B",
            path="/models/mistral-7b",
            size=14000000000,
            format="safetensors",
        )

        db_session.add(model)
        db_session.commit()

        result = model.to_dict()
        assert result["name"] == "Mistral-7B"
        assert result["path"] == "/models/mistral-7b"
        assert result["format"] == "safetensors"
        assert result["supported_engines"] == []
        assert result["metadata"] == {}

    def test_model_repr(self, db_session: Session) -> None:
        """Test Model __repr__ method."""
        model = Model(
            name="Test-Model",
            path="/test/path",
            size=1000000,
            format="pytorch",
        )

        db_session.add(model)
        db_session.commit()

        repr_str = repr(model)
        assert "Model" in repr_str
        assert "Test-Model" in repr_str
        assert "pytorch" in repr_str

    def test_query_models(self, db_session: Session) -> None:
        """Test querying Model records."""
        models = [
            Model(name="Model-A", path="/a", size=1000, format="gguf"),
            Model(name="Model-B", path="/b", size=2000, format="safetensors"),
            Model(name="Model-C", path="/c", size=3000, format="gguf"),
        ]

        db_session.add_all(models)
        db_session.commit()

        # Query all
        all_models = db_session.query(Model).all()
        assert len(all_models) == 3

        # Query by format
        gguf_models = db_session.query(Model).filter(Model.format == "gguf").all()
        assert len(gguf_models) == 2

        # Query by name
        model_a = db_session.query(Model).filter(Model.name == "Model-A").first()
        assert model_a is not None
        assert model_a.size == 1000


class TestService:
    """Tests for the Service class."""

    def test_create_service(self, db_session: Session) -> None:
        """Test creating a Service record."""
        # First create a model
        model = Model(
            name="Test-Model",
            path="/test/path",
            size=1000000,
            format="gguf",
        )
        db_session.add(model)
        db_session.commit()

        # Create service
        service = Service(
            name="test-service",
            model_id=model.id,
            engine="llama.cpp",
            status=ServiceStatus.STOPPED,
        )

        db_session.add(service)
        db_session.commit()

        assert service.id is not None
        assert service.name == "test-service"
        assert service.model_id == model.id
        assert service.engine == "llama.cpp"
        assert service.status == ServiceStatus.STOPPED
        assert service.port is None
        assert service.pid is None
        assert service.created_at is not None

    def test_service_start_stop(self, db_session: Session) -> None:
        """Test Service start and stop methods."""
        service = Service(
            name="test-service",
            engine="llama.cpp",
            status=ServiceStatus.STOPPED,
        )

        db_session.add(service)
        db_session.commit()

        # Start service
        service.start(port=8080, pid=12345)
        db_session.commit()

        assert service.status == ServiceStatus.RUNNING
        assert service.port == 8080
        assert service.pid == 12345
        assert service.started_at is not None

        # Stop service
        service.stop()
        db_session.commit()

        assert service.status == ServiceStatus.STOPPED
        assert service.stopped_at is not None

    def test_service_error(self, db_session: Session) -> None:
        """Test Service set_error method."""
        service = Service(
            name="error-service",
            engine="vllm",
            status=ServiceStatus.STARTING,
        )

        db_session.add(service)
        db_session.commit()

        service.set_error()
        db_session.commit()

        assert service.status == ServiceStatus.ERROR
        assert service.stopped_at is not None

    def test_service_model_relationship(self, db_session: Session) -> None:
        """Test Service-Model relationship."""
        model = Model(
            name="Related-Model",
            path="/related/path",
            size=1000000,
            format="gguf",
        )
        db_session.add(model)
        db_session.commit()

        service = Service(
            name="related-service",
            model_id=model.id,
            engine="llama.cpp",
        )
        db_session.add(service)
        db_session.commit()

        # Test relationship
        assert service.model is not None
        assert service.model.name == "Related-Model"

        # Test backref
        assert model.services[0].name == "related-service"

    def test_query_services_by_status(self, db_session: Session) -> None:
        """Test querying services by status."""
        services = [
            Service(name="running-svc", engine="llama.cpp", status=ServiceStatus.RUNNING),
            Service(name="stopped-svc", engine="vllm", status=ServiceStatus.STOPPED),
            Service(name="error-svc", engine="llama.cpp", status=ServiceStatus.ERROR),
        ]

        db_session.add_all(services)
        db_session.commit()

        running = db_session.query(Service).filter(
            Service.status == ServiceStatus.RUNNING
        ).all()
        assert len(running) == 1
        assert running[0].name == "running-svc"


class TestBenchmarkResult:
    """Tests for the BenchmarkResult class."""

    def test_create_benchmark(self, db_session: Session) -> None:
        """Test creating a BenchmarkResult record."""
        benchmark = BenchmarkResult(
            test_type="performance",
            config=json.dumps({"batch_size": 1, "max_tokens": 100}),
            status=BenchmarkStatus.PENDING,
        )

        db_session.add(benchmark)
        db_session.commit()

        assert benchmark.id is not None
        assert benchmark.test_type == "performance"
        config_dict = json.loads(benchmark.config) if benchmark.config else {}
        assert config_dict["batch_size"] == 1
        assert benchmark.status == BenchmarkStatus.PENDING
        assert benchmark.created_at is not None
        assert benchmark.completed_at is None

    def test_benchmark_complete(self, db_session: Session) -> None:
        """Test BenchmarkResult complete method."""
        benchmark = BenchmarkResult(
            test_type="quality",
            status=BenchmarkStatus.RUNNING,
        )

        db_session.add(benchmark)
        db_session.commit()

        summary = {"score": 0.95, "accuracy": 0.97}
        benchmark.complete(summary=summary)
        db_session.commit()

        assert benchmark.status == BenchmarkStatus.COMPLETED
        # summary is serialized to JSON string
        summary_dict = json.loads(benchmark.summary) if benchmark.summary else {}
        assert summary_dict == summary
        assert benchmark.completed_at is not None

    def test_benchmark_fail(self, db_session: Session) -> None:
        """Test BenchmarkResult fail method."""
        benchmark = BenchmarkResult(
            test_type="latency",
            status=BenchmarkStatus.RUNNING,
        )

        db_session.add(benchmark)
        db_session.commit()

        benchmark.fail()
        db_session.commit()

        assert benchmark.status == BenchmarkStatus.FAILED
        assert benchmark.completed_at is not None


class TestRequestLog:
    """Tests for the RequestLog class."""

    def test_create_request_log(self, db_session: Session) -> None:
        """Test creating a RequestLog record."""
        log = RequestLog(
            request_id="req-12345",
            api_type="chat",
            model="LLaMA-2-7B",
            prompt_length=100,
            prompt_content="Hello, how are you?",
            parameters=json.dumps({"temperature": 0.7, "max_tokens": 100}),
            status="pending",
        )

        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.request_id == "req-12345"
        assert log.api_type == "chat"
        assert log.model == "LLaMA-2-7B"
        assert log.prompt_length == 100
        assert log.prompt_content == "Hello, how are you?"
        params = json.loads(log.parameters) if log.parameters else {}
        assert params["temperature"] == 0.7
        assert log.timestamp is not None

    def test_request_log_unique_request_id(self, db_session: Session) -> None:
        """Test that request_id must be unique."""
        log1 = RequestLog(
            request_id="unique-req-id",
            api_type="chat",
            model="Model-A",
        )

        db_session.add(log1)
        db_session.commit()

        log2 = RequestLog(
            request_id="unique-req-id",  # Same request_id
            api_type="completion",
            model="Model-B",
        )

        db_session.add(log2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_request_log_service_relationship(self, db_session: Session) -> None:
        """Test RequestLog-Service relationship."""
        model = Model(name="Test", path="/test", size=1000, format="gguf")
        db_session.add(model)
        db_session.commit()

        service = Service(name="test-svc", model_id=model.id, engine="llama.cpp")
        db_session.add(service)
        db_session.commit()

        log = RequestLog(
            request_id="req-with-service",
            api_type="chat",
            model="Test",
            service_id=service.id,
        )
        db_session.add(log)
        db_session.commit()

        assert log.service is not None
        assert log.service.name == "test-svc"


class TestResponseLog:
    """Tests for the ResponseLog class."""

    def test_create_response_log(self, db_session: Session) -> None:
        """Test creating a ResponseLog record."""
        # First create a request log
        request_log = RequestLog(
            request_id="req-67890",
            api_type="completion",
            model="Mistral-7B",
            prompt_length=50,
        )
        db_session.add(request_log)
        db_session.commit()

        # Create response log
        response_log = ResponseLog(
            request_id="req-67890",
            status="success",
            output_length=200,
            output_content="This is the generated response.",
            total_time=1.5,
            prefill_time=0.1,
            prefill_tokens=50,
            decode_time=1.4,
            decode_tokens=200,
            ttft=0.15,
            tpot=0.007,
            gpu_util=85.5,
            memory_used=12.3,
        )

        db_session.add(response_log)
        db_session.commit()

        assert response_log.id is not None
        assert response_log.request_id == "req-67890"
        assert response_log.status == "success"
        assert response_log.output_length == 200
        assert response_log.total_time == 1.5
        assert response_log.ttft == 0.15
        assert response_log.gpu_util == 85.5

    def test_response_request_relationship(self, db_session: Session) -> None:
        """Test ResponseLog-RequestLog relationship."""
        request_log = RequestLog(
            request_id="req-rel-test",
            api_type="chat",
            model="Test-Model",
        )
        db_session.add(request_log)
        db_session.commit()

        response_log = ResponseLog(
            request_id="req-rel-test",
            status="success",
            output_length=100,
        )
        db_session.add(response_log)
        db_session.commit()

        # Test relationship
        assert response_log.request is not None
        assert response_log.request.request_id == "req-rel-test"

        # Test back_populates
        assert request_log.response is not None
        assert request_log.response.status == "success"

    def test_query_logs_by_timestamp(self, db_session: Session) -> None:
        """Test querying logs by timestamp range."""
        log1 = RequestLog(
            request_id="req-time-1",
            api_type="chat",
            model="Model-A",
        )
        db_session.add(log1)
        db_session.commit()

        log2 = RequestLog(
            request_id="req-time-2",
            api_type="chat",
            model="Model-B",
        )
        db_session.add(log2)
        db_session.commit()

        # Query all logs
        all_logs = db_session.query(RequestLog).all()
        assert len(all_logs) == 2

        # Query by model
        model_a_logs = db_session.query(RequestLog).filter(
            RequestLog.model == "Model-A"
        ).all()
        assert len(model_a_logs) == 1
