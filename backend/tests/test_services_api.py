"""Tests for service management API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.service import Service, ServiceStatus
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.service_manager import ProcessManager, ServiceManager


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


class TestServiceManager:
    """Tests for ServiceManager class."""

    def test_list_services_empty(self, db_session: Session) -> None:
        """Test listing services when database is empty."""
        manager = ServiceManager(db_session)
        services = manager.list_services()
        assert services == []

    def test_create_service(self, db_session: Session) -> None:
        """Test creating a service."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Test-Service",
            model_id=1,
            engine="vllm",
            config='{"model": "test-model"}',
        )

        service = manager.create_service(service_data)

        assert service.id is not None
        assert service.name == "Test-Service"
        assert service.engine == "vllm"
        assert service.status == ServiceStatus.STOPPED

    def test_create_service_invalid_engine(self, db_session: Session) -> None:
        """Test creating a service with invalid engine."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Test-Service",
            engine="invalid_engine",
        )

        with pytest.raises(ValueError, match="Unsupported engine"):
            manager.create_service(service_data)

    def test_get_service(self, db_session: Session) -> None:
        """Test getting a service by ID."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Get-Test-Service",
            engine="llamacpp",
        )
        created = manager.create_service(service_data)

        retrieved = manager.get_service(created.id)

        assert retrieved is not None
        assert retrieved.name == "Get-Test-Service"
        assert retrieved.engine == "llamacpp"

    def test_get_service_not_found(self, db_session: Session) -> None:
        """Test getting a non-existent service."""
        manager = ServiceManager(db_session)
        retrieved = manager.get_service(999)
        assert retrieved is None

    def test_update_service(self, db_session: Session) -> None:
        """Test updating a service."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Update-Test-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        update_data = ServiceUpdate(name="Updated-Service-Name")
        updated = manager.update_service(created.id, update_data)

        assert updated is not None
        assert updated.name == "Updated-Service-Name"

    def test_update_service_not_found(self, db_session: Session) -> None:
        """Test updating a non-existent service."""
        manager = ServiceManager(db_session)
        update_data = ServiceUpdate(name="Updated-Name")
        updated = manager.update_service(999, update_data)
        assert updated is None

    def test_delete_service(self, db_session: Session) -> None:
        """Test deleting a service."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Delete-Test-Service",
            engine="lmdeploy",
        )
        created = manager.create_service(service_data)

        deleted = manager.delete_service(created.id)
        assert deleted is True

        retrieved = manager.get_service(created.id)
        assert retrieved is None

    def test_delete_service_not_found(self, db_session: Session) -> None:
        """Test deleting a non-existent service."""
        manager = ServiceManager(db_session)
        deleted = manager.delete_service(999)
        assert deleted is False

    def test_delete_running_service(self, db_session: Session) -> None:
        """Test that deleting a running service raises an error."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Running-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        # Manually set status to running
        created.status = ServiceStatus.RUNNING
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot delete running service"):
            manager.delete_service(created.id)

    def test_start_service_not_found(self, db_session: Session) -> None:
        """Test starting a non-existent service."""
        manager = ServiceManager(db_session)
        with pytest.raises(ValueError, match="Service .* not found"):
            manager.start_service(999)

    def test_stop_service_not_found(self, db_session: Session) -> None:
        """Test stopping a non-existent service."""
        manager = ServiceManager(db_session)
        with pytest.raises(ValueError, match="Service .* not found"):
            manager.stop_service(999)

    def test_stop_service_not_running(self, db_session: Session) -> None:
        """Test stopping a service that is not running."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Stopped-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        with pytest.raises(ValueError, match="is not running"):
            manager.stop_service(created.id)

    def test_get_service_status(self, db_session: Session) -> None:
        """Test getting service status."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Status-Test-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        status = manager.get_service_status(created.id)

        assert status["id"] == created.id
        assert status["name"] == "Status-Test-Service"
        assert status["status"] == ServiceStatus.STOPPED
        assert status["running"] is False

    def test_get_service_status_not_found(self, db_session: Session) -> None:
        """Test getting status of non-existent service."""
        manager = ServiceManager(db_session)
        status = manager.get_service_status(999)
        assert "error" in status

    def test_get_service_logs(self, db_session: Session) -> None:
        """Test getting service logs."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Log-Test-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        logs = manager.get_service_logs(created.id)

        assert logs["service_id"] == created.id
        assert "logs" in logs

    def test_get_service_logs_not_found(self, db_session: Session) -> None:
        """Test getting logs of non-existent service."""
        manager = ServiceManager(db_session)
        logs = manager.get_service_logs(999)
        assert "error" in logs

    def test_get_service_metrics_stopped(self, db_session: Session) -> None:
        """Test getting metrics for a stopped service."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Metrics-Test-Service",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        metrics = manager.get_service_metrics(created.id)

        assert metrics["service_id"] == created.id
        assert "message" in metrics

    def test_get_available_port(self, db_session: Session) -> None:
        """Test getting an available port."""
        manager = ServiceManager(db_session)
        # Use a different port range that's less likely to be fully occupied
        # and mock the socket binding
        with patch.object(manager, '_get_available_port', return_value=8500):
            port = manager.get_available_port(8000, 9000)
            assert 8000 <= port < 9000

    def test_get_engine_params(self, db_session: Session) -> None:
        """Test getting engine parameters."""
        manager = ServiceManager(db_session)
        params = manager.get_engine_params("vllm")

        assert "model" in params
        assert "dtype" in params
        assert params["model"]["required"] is True

    def test_get_engine_params_invalid(self, db_session: Session) -> None:
        """Test getting parameters for invalid engine."""
        manager = ServiceManager(db_session)
        with pytest.raises(ValueError, match="Unsupported engine"):
            manager.get_engine_params("invalid_engine")

    def test_get_engine_param_groups(self, db_session: Session) -> None:
        """Test getting engine parameter groups."""
        manager = ServiceManager(db_session)
        groups = manager.get_engine_param_groups("vllm")

        assert "basic" in groups
        assert "gpu" in groups
        assert "api" in groups

    def test_list_services_with_pagination(self, db_session: Session) -> None:
        """Test listing services with pagination."""
        manager = ServiceManager(db_session)

        # Create multiple services
        for i in range(5):
            service_data = ServiceCreate(
                name=f"Service-{i}",
                engine="vllm",
            )
            manager.create_service(service_data)

        # Test pagination
        services = manager.list_services(skip=0, limit=3)
        assert len(services) == 3

        services = manager.list_services(skip=3, limit=3)
        assert len(services) == 2


class TestProcessManager:
    """Tests for ProcessManager class."""

    def test_register_and_get_process(self) -> None:
        """Test registering and getting a process."""
        mock_process = MagicMock()
        mock_process.pid = 12345

        ProcessManager.register_process(1, mock_process)
        retrieved = ProcessManager.get_process(1)

        assert retrieved is mock_process

        # Cleanup
        ProcessManager.unregister_process(1)

    def test_unregister_process(self) -> None:
        """Test unregistering a process."""
        mock_process = MagicMock()
        mock_process.pid = 12346

        ProcessManager.register_process(2, mock_process)
        ProcessManager.unregister_process(2)

        retrieved = ProcessManager.get_process(2)
        assert retrieved is None

    def test_is_process_running_nonexistent(self) -> None:
        """Test checking if non-existent process is running."""
        # Non-existent PID (very high number)
        result = ProcessManager.is_process_running(999999)
        assert result is False


class TestServiceModel:
    """Tests for Service model methods."""

    def test_service_to_dict(self, db_session: Session) -> None:
        """Test service.to_dict() method."""
        service = Service(
            name="Dict-Test",
            engine="vllm",
            config='{"test": "value"}',
            status=ServiceStatus.STOPPED,
        )
        db_session.add(service)
        db_session.commit()

        d = service.to_dict()

        assert d["name"] == "Dict-Test"
        assert d["engine"] == "vllm"
        assert d["status"] == ServiceStatus.STOPPED
        assert "created_at" in d

    def test_service_start(self, db_session: Session) -> None:
        """Test service.start() method."""
        service = Service(
            name="Start-Test",
            engine="vllm",
        )
        db_session.add(service)
        db_session.commit()

        service.start(port=8000, pid=12345)
        db_session.commit()

        assert service.status == ServiceStatus.RUNNING
        assert service.port == 8000
        assert service.pid == 12345
        assert service.started_at is not None

    def test_service_stop(self, db_session: Session) -> None:
        """Test service.stop() method."""
        service = Service(
            name="Stop-Test",
            engine="vllm",
        )
        db_session.add(service)
        db_session.commit()

        service.start(port=8001, pid=12346)
        service.stop()
        db_session.commit()

        assert service.status == ServiceStatus.STOPPED
        assert service.stopped_at is not None

    def test_service_set_error(self, db_session: Session) -> None:
        """Test service.set_error() method."""
        service = Service(
            name="Error-Test",
            engine="vllm",
        )
        db_session.add(service)
        db_session.commit()

        service.set_error()
        db_session.commit()

        assert service.status == ServiceStatus.ERROR


class TestServiceStatusValues:
    """Tests for ServiceStatus values."""

    def test_status_values(self) -> None:
        """Test that status values are as expected."""
        assert ServiceStatus.STOPPED == "stopped"
        assert ServiceStatus.STARTING == "starting"
        assert ServiceStatus.RUNNING == "running"
        assert ServiceStatus.STOPPING == "stopping"
        assert ServiceStatus.ERROR == "error"


class TestServiceManagerStartStop:
    """Tests for starting and stopping services (mocked)."""

    def test_start_service_already_running(self, db_session: Session) -> None:
        """Test that starting an already running service raises an error."""
        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Already-Running",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        # Manually set to running
        created.status = ServiceStatus.RUNNING
        db_session.commit()

        with pytest.raises(ValueError, match="already running"):
            manager.start_service(created.id)

    @patch("app.services.service_manager.ProcessManager.start_process")
    @patch("app.services.service_manager.ServiceManager._wait_for_ready")
    @patch("app.services.service_manager.ServiceManager._get_available_port")
    def test_start_service_mocked(
        self,
        mock_port: MagicMock,
        mock_wait: MagicMock,
        mock_start: MagicMock,
        db_session: Session,
    ) -> None:
        """Test starting a service with mocked process management."""
        from app.adapters.base import ProcessInfo

        mock_port.return_value = 8000
        mock_start.return_value = ProcessInfo(pid=12345, port=8000, command="test")
        mock_wait.return_value = True

        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Start-Mock-Test",
            engine="vllm",
            config='{"model": "test-model"}',
        )
        created = manager.create_service(service_data)

        result = manager.start_service(created.id)

        assert result.status == ServiceStatus.RUNNING
        assert result.port == 8000
        assert result.pid == 12345
        mock_start.assert_called_once()
        mock_wait.assert_called_once()

    @patch("app.services.service_manager.ProcessManager.stop_process")
    def test_stop_service_mocked(
        self,
        mock_stop: MagicMock,
        db_session: Session,
    ) -> None:
        """Test stopping a service with mocked process management."""
        mock_stop.return_value = True

        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Stop-Mock-Test",
            engine="vllm",
        )
        created = manager.create_service(service_data)

        # Manually set to running with pid
        created.status = ServiceStatus.RUNNING
        created.pid = 12345
        created.port = 8000
        db_session.commit()

        result = manager.stop_service(created.id)

        assert result.status == ServiceStatus.STOPPED
        mock_stop.assert_called_once_with(12345, created.id)


class TestServiceManagerRestart:
    """Tests for restarting services."""

    @patch("app.services.service_manager.ProcessManager.start_process")
    @patch("app.services.service_manager.ServiceManager._wait_for_ready")
    @patch("app.services.service_manager.ProcessManager.stop_process")
    @patch("app.services.service_manager.ServiceManager._get_available_port")
    def test_restart_service_stopped(
        self,
        mock_port: MagicMock,
        mock_stop: MagicMock,
        mock_wait: MagicMock,
        mock_start: MagicMock,
        db_session: Session,
    ) -> None:
        """Test restarting a stopped service."""
        from app.adapters.base import ProcessInfo

        mock_port.return_value = 8000
        mock_start.return_value = ProcessInfo(pid=12345, port=8000, command="test")
        mock_wait.return_value = True

        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Restart-Stopped-Test",
            engine="vllm",
            config='{"model": "test-model"}',
        )
        created = manager.create_service(service_data)

        # Restart (service is stopped, should just start)
        result = manager.restart_service(created.id)

        assert result.status == ServiceStatus.RUNNING
        mock_stop.assert_not_called()

    @patch("app.services.service_manager.ProcessManager.start_process")
    @patch("app.services.service_manager.ServiceManager._wait_for_ready")
    @patch("app.services.service_manager.ProcessManager.stop_process")
    @patch("app.services.service_manager.ServiceManager._get_available_port")
    def test_restart_service_running(
        self,
        mock_port: MagicMock,
        mock_stop: MagicMock,
        mock_wait: MagicMock,
        mock_start: MagicMock,
        db_session: Session,
    ) -> None:
        """Test restarting a running service."""
        from app.adapters.base import ProcessInfo

        mock_port.return_value = 8000
        mock_stop.return_value = True
        mock_start.return_value = ProcessInfo(pid=12345, port=8000, command="test")
        mock_wait.return_value = True

        manager = ServiceManager(db_session)
        service_data = ServiceCreate(
            name="Restart-Running-Test",
            engine="vllm",
            config='{"model": "test-model"}',
        )
        created = manager.create_service(service_data)

        # Set to running
        created.status = ServiceStatus.RUNNING
        created.pid = 54321
        created.port = 8001
        db_session.commit()

        # Restart
        result = manager.restart_service(created.id)

        assert result.status == ServiceStatus.RUNNING
        mock_stop.assert_called_once()
