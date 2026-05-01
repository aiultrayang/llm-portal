"""Tests for log management API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.log import RequestLog, ResponseLog
from app.services.log_service import LogService


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory SQLite database for testing.

    Yields:
        Session: A SQLAlchemy session connected to the test database.
    """
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


class TestLogService:
    """Tests for LogService class."""

    def test_generate_request_id(self, db_session: Session) -> None:
        """Test generating unique request IDs."""
        service = LogService(db_session)
        id1 = service.generate_request_id()
        id2 = service.generate_request_id()

        assert id1 != id2
        assert len(id1) == 32  # UUID hex format

    def test_create_request_log(self, db_session: Session) -> None:
        """Test creating a request log."""
        service = LogService(db_session)

        log = service.create_request_log(
            request_id="test-req-001",
            api_type="chat",
            model="test-model",
            service_id=1,
            prompt_length=100,
            prompt_content="Hello, how are you?",
            parameters={"temperature": 0.7, "max_tokens": 100},
            status="pending"
        )

        assert log.id is not None
        assert log.request_id == "test-req-001"
        assert log.api_type == "chat"
        assert log.model == "test-model"
        assert log.service_id == 1
        assert log.prompt_length == 100
        assert log.prompt_content == "Hello, how are you?"
        assert log.status == "pending"

    def test_create_response_log(self, db_session: Session) -> None:
        """Test creating a response log."""
        service = LogService(db_session)

        # First create a request log
        service.create_request_log(
            request_id="test-req-002",
            api_type="chat",
            model="test-model",
            service_id=1,
            prompt_length=50,
            prompt_content="Test prompt",
            parameters={},
            status="pending"
        )

        # Create response log
        response_log = service.create_response_log(
            request_id="test-req-002",
            status="success",
            output_length=200,
            output_content="Test response content",
            total_time=1.5,
            prefill_time=0.3,
            prefill_tokens=50,
            decode_time=1.2,
            decode_tokens=150,
            ttft=0.35,
            tpot=0.008,
            gpu_util=85.5,
            memory_used=4096
        )

        assert response_log.id is not None
        assert response_log.request_id == "test-req-002"
        assert response_log.status == "success"
        assert response_log.output_length == 200
        assert response_log.total_time == 1.5
        assert response_log.ttft == 0.35
        assert response_log.tpot == 0.008
        assert response_log.gpu_util == 85.5

        # Check that request status was updated
        request_log = db_session.query(RequestLog).filter(
            RequestLog.request_id == "test-req-002"
        ).first()
        assert request_log.status == "success"

    def test_query_request_logs(self, db_session: Session) -> None:
        """Test querying request logs."""
        service = LogService(db_session)

        # Create multiple request logs
        for i in range(5):
            service.create_request_log(
                request_id=f"test-req-{i:03d}",
                api_type="chat" if i % 2 == 0 else "completion",
                model=f"model-{i % 2}",
                service_id=1,
                prompt_length=100 * (i + 1),
                prompt_content=f"Prompt {i}",
                parameters={},
                status="pending" if i < 3 else "success"
            )

        # Query all logs
        logs = service.query_logs(log_type="request")
        assert len(logs) == 5

        # Query with model filter
        logs = service.query_logs(log_type="request", model="model-0")
        assert len(logs) == 3

        # Query with status filter
        logs = service.query_logs(log_type="request", status="pending")
        assert len(logs) == 3

        # Query with limit and offset
        logs = service.query_logs(log_type="request", limit=2, offset=1)
        assert len(logs) == 2

    def test_query_response_logs(self, db_session: Session) -> None:
        """Test querying response logs."""
        service = LogService(db_session)

        # Create request and response logs
        for i in range(3):
            service.create_request_log(
                request_id=f"test-req-resp-{i:03d}",
                api_type="chat",
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content=f"Prompt {i}",
                parameters={},
                status="pending"
            )
            service.create_response_log(
                request_id=f"test-req-resp-{i:03d}",
                status="success" if i < 2 else "error",
                output_length=200,
                output_content=f"Response {i}",
                total_time=1.0,
                prefill_time=0.2,
                prefill_tokens=100,
                decode_time=0.8,
                decode_tokens=100,
                ttft=0.25,
                tpot=0.008,
                gpu_util=80.0,
                memory_used=4096
            )

        # Query all response logs
        logs = service.query_logs(log_type="response")
        assert len(logs) == 3

        # Query with status filter
        logs = service.query_logs(log_type="response", status="success")
        assert len(logs) == 2

    def test_get_log_detail(self, db_session: Session) -> None:
        """Test getting complete log details."""
        service = LogService(db_session)

        # Create request and response logs
        service.create_request_log(
            request_id="test-detail-001",
            api_type="chat",
            model="test-model",
            service_id=1,
            prompt_length=100,
            prompt_content="Test prompt",
            parameters={"temperature": 0.7},
            status="success"
        )
        service.create_response_log(
            request_id="test-detail-001",
            status="success",
            output_length=200,
            output_content="Test response",
            total_time=1.5,
            prefill_time=0.3,
            prefill_tokens=100,
            decode_time=1.2,
            decode_tokens=100,
            ttft=0.35,
            tpot=0.012,
            gpu_util=85.0,
            memory_used=4096
        )

        detail = service.get_log_detail("test-detail-001")

        assert detail is not None
        assert detail["request"]["request_id"] == "test-detail-001"
        assert detail["request"]["model"] == "test-model"
        assert detail["response"]["status"] == "success"
        assert detail["response"]["total_time"] == 1.5

    def test_get_log_detail_not_found(self, db_session: Session) -> None:
        """Test getting log detail for non-existent request."""
        service = LogService(db_session)
        detail = service.get_log_detail("non-existent-id")
        assert detail is None

    def test_get_log_stats(self, db_session: Session) -> None:
        """Test getting log statistics."""
        service = LogService(db_session)

        # Create multiple request and response logs
        for i in range(5):
            service.create_request_log(
                request_id=f"test-stats-{i:03d}",
                api_type="chat" if i % 2 == 0 else "completion",
                model=f"model-{i % 2}",
                service_id=1,
                prompt_length=100,
                prompt_content=f"Prompt {i}",
                parameters={},
                status="success" if i < 4 else "error"
            )
            service.create_response_log(
                request_id=f"test-stats-{i:03d}",
                status="success" if i < 4 else "error",
                output_length=200,
                output_content=f"Response {i}",
                total_time=1.0 + i * 0.1,
                prefill_time=0.2,
                prefill_tokens=100,
                decode_time=0.8,
                decode_tokens=100,
                ttft=0.25 + i * 0.01,
                tpot=0.008,
                gpu_util=80.0 + i,
                memory_used=4096
            )

        stats = service.get_log_stats(group_by="model")

        assert stats["total_requests"] == 5
        assert stats["success_rate"] == 80.0  # 4 out of 5
        assert stats["avg_response_time"] > 0
        assert stats["avg_ttft"] > 0
        assert len(stats["grouped_stats"]) == 2  # Two models

    def test_get_log_stats_empty(self, db_session: Session) -> None:
        """Test getting log statistics when no logs exist."""
        service = LogService(db_session)
        stats = service.get_log_stats()

        assert stats["total_requests"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_response_time"] == 0.0
        assert stats["grouped_stats"] == []

    def test_get_log_stats_group_by_api_type(self, db_session: Session) -> None:
        """Test grouping log statistics by API type."""
        service = LogService(db_session)

        # Create logs with different API types
        for i in range(4):
            service.create_request_log(
                request_id=f"test-api-type-{i:03d}",
                api_type="chat" if i < 3 else "embedding",
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content=f"Prompt {i}",
                parameters={},
                status="success"
            )
            service.create_response_log(
                request_id=f"test-api-type-{i:03d}",
                status="success",
                output_length=100,
                output_content=f"Response {i}",
                total_time=1.0,
                prefill_time=0.2,
                prefill_tokens=100,
                decode_time=0.8,
                decode_tokens=100,
                ttft=0.25,
                tpot=0.008,
                gpu_util=80.0,
                memory_used=4096
            )

        stats = service.get_log_stats(group_by="api_type")

        assert len(stats["grouped_stats"]) == 2
        api_types = [s["key"] for s in stats["grouped_stats"]]
        assert "chat" in api_types
        assert "embedding" in api_types

    def test_export_logs_json(self, db_session: Session) -> None:
        """Test exporting logs in JSON format."""
        service = LogService(db_session)

        # Create request logs
        for i in range(3):
            service.create_request_log(
                request_id=f"test-export-{i:03d}",
                api_type="chat",
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content=f"Prompt {i}",
                parameters={},
                status="success"
            )

        exported = service.export_logs(format="json", log_type="request")

        assert exported is not None
        assert "test-export-000" in exported
        assert "test-export-001" in exported
        assert "test-export-002" in exported

    def test_export_logs_csv(self, db_session: Session) -> None:
        """Test exporting logs in CSV format."""
        service = LogService(db_session)

        # Create request logs
        service.create_request_log(
            request_id="test-csv-001",
            api_type="chat",
            model="test-model",
            service_id=1,
            prompt_length=100,
            prompt_content="Test prompt",
            parameters={},
            status="success"
        )

        exported = service.export_logs(format="csv", log_type="request")

        assert exported is not None
        assert "test-csv-001" in exported
        assert "test-model" in exported

    def test_export_logs_empty(self, db_session: Session) -> None:
        """Test exporting logs when no logs exist."""
        service = LogService(db_session)
        exported = service.export_logs(format="json", log_type="request")
        assert exported == "[]"

    def test_cleanup_logs(self, db_session: Session) -> None:
        """Test cleaning up old logs."""
        service = LogService(db_session)

        # Create some old logs
        old_time = datetime.utcnow() - timedelta(days=30)

        # Create old request log
        old_log = RequestLog(
            request_id="old-log-001",
            api_type="chat",
            model="old-model",
            service_id=1,
            prompt_length=100,
            prompt_content="Old prompt",
            parameters=None,
            status="success",
            timestamp=old_time
        )
        db_session.add(old_log)
        db_session.commit()

        # Create old response log
        old_response = ResponseLog(
            request_id="old-log-001",
            status="success",
            output_length=100,
            output_content="Old response",
            total_time=1.0,
            prefill_time=0.2,
            prefill_tokens=100,
            decode_time=0.8,
            decode_tokens=100,
            ttft=0.25,
            tpot=0.008,
            gpu_util=80.0,
            memory_used=4096,
            timestamp=old_time
        )
        db_session.add(old_response)
        db_session.commit()

        # Create a new log
        service.create_request_log(
            request_id="new-log-001",
            api_type="chat",
            model="new-model",
            service_id=1,
            prompt_length=100,
            prompt_content="New prompt",
            parameters={},
            status="success"
        )

        # Cleanup logs older than 15 days
        before_date = datetime.utcnow() - timedelta(days=15)
        deleted_count = service.cleanup_logs(before_date)

        assert deleted_count == 2  # 1 request log + 1 response log

        # Verify new log still exists
        remaining = service.query_logs(log_type="request")
        assert len(remaining) == 1
        assert remaining[0].request_id == "new-log-001"

    def test_get_models(self, db_session: Session) -> None:
        """Test getting distinct model names."""
        service = LogService(db_session)

        # Create logs with different models
        models_list = ["model-a", "model-b", "model-a", "model-c"]
        for i, model in enumerate(models_list):
            service.create_request_log(
                request_id=f"test-models-{i:03d}",
                api_type="chat",
                model=model,
                service_id=1,
                prompt_length=100,
                prompt_content="Test",
                parameters={},
                status="success"
            )

        models = service.get_models()

        assert len(models) == 3
        assert "model-a" in models
        assert "model-b" in models
        assert "model-c" in models

    def test_get_api_types(self, db_session: Session) -> None:
        """Test getting distinct API types."""
        service = LogService(db_session)

        # Create logs with different API types
        api_types_list = ["chat", "completion", "chat", "embedding"]
        for i, api_type in enumerate(api_types_list):
            service.create_request_log(
                request_id=f"test-api-{i:03d}",
                api_type=api_type,
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content="Test",
                parameters={},
                status="success"
            )

        api_types = service.get_api_types()

        assert len(api_types) == 3
        assert "chat" in api_types
        assert "completion" in api_types
        assert "embedding" in api_types

    def test_get_statuses(self, db_session: Session) -> None:
        """Test getting distinct statuses."""
        service = LogService(db_session)

        # Create logs with different statuses
        statuses_list = ["pending", "success", "error", "success"]
        for i, status in enumerate(statuses_list):
            service.create_request_log(
                request_id=f"test-status-{i:03d}",
                api_type="chat",
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content="Test",
                parameters={},
                status=status
            )

        statuses = service.get_statuses()

        assert len(statuses) == 3
        assert "pending" in statuses
        assert "success" in statuses
        assert "error" in statuses

    def test_query_logs_with_time_filter(self, db_session: Session) -> None:
        """Test querying logs with time filters."""
        service = LogService(db_session)

        # Create logs
        now = datetime.utcnow()
        for i in range(3):
            service.create_request_log(
                request_id=f"test-time-{i:03d}",
                api_type="chat",
                model="test-model",
                service_id=1,
                prompt_length=100,
                prompt_content="Test",
                parameters={},
                status="success"
            )

        # Query with start_time
        start_time = now - timedelta(hours=1)
        logs = service.query_logs(log_type="request", start_time=start_time)
        assert len(logs) == 3

        # Query with end_time
        end_time = now + timedelta(hours=1)
        logs = service.query_logs(log_type="request", end_time=end_time)
        assert len(logs) == 3

        # Query with time range that excludes all logs
        future_start = now + timedelta(hours=1)
        logs = service.query_logs(log_type="request", start_time=future_start)
        assert len(logs) == 0


class TestLogServiceIntegration:
    """Integration tests for LogService."""

    def test_full_request_response_cycle(self, db_session: Session) -> None:
        """Test the full cycle of creating request and response logs."""
        service = LogService(db_session)

        # Generate request ID
        request_id = service.generate_request_id()

        # Create request log
        request_log = service.create_request_log(
            request_id=request_id,
            api_type="chat",
            model="llama-3-70b",
            service_id=1,
            prompt_length=500,
            prompt_content="Explain quantum computing in simple terms.",
            parameters={"temperature": 0.7, "max_tokens": 1000, "top_p": 0.9},
            status="pending"
        )

        assert request_log.status == "pending"

        # Simulate processing and create response log
        response_log = service.create_response_log(
            request_id=request_id,
            status="success",
            output_length=800,
            output_content="Quantum computing is a type of computing that uses quantum mechanics...",
            total_time=3.5,
            prefill_time=0.5,
            prefill_tokens=500,
            decode_time=3.0,
            decode_tokens=800,
            ttft=0.55,
            tpot=0.00375,
            gpu_util=92.5,
            memory_used=45056
        )

        assert response_log.status == "success"

        # Get full details
        detail = service.get_log_detail(request_id)
        assert detail["request"]["status"] == "success"  # Updated
        assert detail["response"]["output_length"] == 800

        # Get stats
        stats = service.get_log_stats()
        assert stats["total_requests"] == 1
        assert stats["success_rate"] == 100.0

    def test_concurrent_requests(self, db_session: Session) -> None:
        """Test handling multiple concurrent requests."""
        service = LogService(db_session)

        # Create multiple requests
        request_ids = []
        for i in range(10):
            request_id = service.generate_request_id()
            request_ids.append(request_id)

            service.create_request_log(
                request_id=request_id,
                api_type="chat",
                model=f"model-{i % 3}",
                service_id=1,
                prompt_length=100 * i,
                prompt_content=f"Prompt {i}",
                parameters={},
                status="pending"
            )

        # Create responses for half of them
        for i, request_id in enumerate(request_ids[:5]):
            service.create_response_log(
                request_id=request_id,
                status="success" if i % 2 == 0 else "error",
                output_length=200,
                output_content=f"Response {i}",
                total_time=1.0,
                prefill_time=0.2,
                prefill_tokens=100,
                decode_time=0.8,
                decode_tokens=100,
                ttft=0.25,
                tpot=0.008,
                gpu_util=80.0,
                memory_used=4096
            )

        # Query pending requests
        pending = service.query_logs(log_type="request", status="pending")
        assert len(pending) == 5

        # Query success responses
        success = service.query_logs(log_type="response", status="success")
        assert len(success) == 3

        # Check stats
        stats = service.get_log_stats(group_by="model")
        assert stats["total_requests"] == 10
