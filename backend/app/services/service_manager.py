"""Service Manager - Business logic for managing LLM service instances."""

import json
import os
import signal
import socket
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.adapters import LMDeployAdapter, LlamaCppAdapter, VLLMAdapter
from app.adapters.base import BaseEngineAdapter, ProcessInfo
from app.config import LOGS_DIR
from app.models.service import Service as ServiceModel
from app.models.service import ServiceStatus
from app.schemas.service import ServiceCreate, ServiceUpdate


class ProcessManager:
    """Manages subprocess lifecycle for LLM services."""

    # Class-level storage for active processes
    # Maps service_id -> subprocess.Popen
    _active_processes: Dict[int, subprocess.Popen] = {}

    @classmethod
    def get_process(cls, service_id: int) -> Optional[subprocess.Popen]:
        """Get the active process for a service."""
        return cls._active_processes.get(service_id)

    @classmethod
    def register_process(cls, service_id: int, process: subprocess.Popen) -> None:
        """Register a process for a service."""
        cls._active_processes[service_id] = process

    @classmethod
    def unregister_process(cls, service_id: int) -> None:
        """Unregister a process for a service."""
        cls._active_processes.pop(service_id, None)

    @classmethod
    def start_process(
        cls,
        command: str,
        port: int,
        service_id: int,
        log_file: Optional[str] = None
    ) -> ProcessInfo:
        """
        Start a subprocess for an LLM service.

        Args:
            command: The shell command to execute
            port: The port the service will listen on
            service_id: The service ID for tracking
            log_file: Optional path to log file

        Returns:
            ProcessInfo with pid, port, and command
        """
        # Prepare log file
        if log_file is None:
            log_file = str(LOGS_DIR / f"service_{service_id}.log")

        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Open log file for writing
        log_fh = open(log_file, 'a')

        # Start the process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,  # Create new process group for proper termination
            start_new_session=True
        )

        # Register the process
        cls.register_process(service_id, process)

        return ProcessInfo(pid=process.pid, port=port, command=command)

    @classmethod
    def stop_process(cls, pid: int, service_id: int) -> bool:
        """
        Stop a subprocess by sending SIGTERM to the process group.

        Args:
            pid: The process ID
            service_id: The service ID

        Returns:
            True if the process was stopped, False otherwise
        """
        try:
            # Get the process group ID
            pgid = os.getpgid(pid)

            # Send SIGTERM to the entire process group
            os.killpg(pgid, signal.SIGTERM)

            # Wait a bit for graceful shutdown
            time.sleep(2)

            # Check if process is still running
            try:
                os.kill(pid, 0)
                # Process still running, force kill
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                # Process has terminated
                pass

            # Unregister the process
            cls.unregister_process(service_id)
            return True

        except (ProcessLookupError, OSError):
            # Process already terminated
            cls.unregister_process(service_id)
            return True

        except Exception as e:
            print(f"Error stopping process {pid}: {e}")
            return False

    @classmethod
    def is_process_running(cls, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class ServiceManager:
    """Business logic for managing LLM service instances."""

    # Engine adapter registry
    ADAPTERS: Dict[str, type] = {
        "vllm": VLLMAdapter,
        "lmdeploy": LMDeployAdapter,
        "llamacpp": LlamaCppAdapter,
    }

    def __init__(self, db: Session):
        """Initialize the service manager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

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

    def _get_available_port(self, start_port: int = 8000, end_port: int = 9000) -> int:
        """Find an available port in the given range.

        Args:
            start_port: The starting port number
            end_port: The ending port number

        Returns:
            An available port number
        """
        for port in range(start_port, end_port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"No available ports found in range {start_port}-{end_port}")

    def _wait_for_ready(
        self,
        port: int,
        health_url: str,
        timeout: int = 120,
        poll_interval: float = 2.0
    ) -> bool:
        """Wait for the service to become ready.

        Args:
            port: The service port
            health_url: The health check URL
            timeout: Maximum wait time in seconds
            poll_interval: Interval between health checks

        Returns:
            True if the service is ready, False if timeout
        """
        start_time = time.time()
        full_url = health_url.format(port=port)

        while time.time() - start_time < timeout:
            try:
                response = requests.get(full_url, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass

            time.sleep(poll_interval)

        return False

    def list_services(self, skip: int = 0, limit: int = 100) -> List[ServiceModel]:
        """Get a list of all services.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Service model instances
        """
        return self.db.query(ServiceModel).offset(skip).limit(limit).all()

    def get_service(self, service_id: int) -> Optional[ServiceModel]:
        """Get a service by ID.

        Args:
            service_id: The service ID

        Returns:
            The Service model instance or None
        """
        return self.db.query(ServiceModel).filter(ServiceModel.id == service_id).first()

    def create_service(self, service_data: ServiceCreate) -> ServiceModel:
        """Create a new service instance.

        Args:
            service_data: The service creation data

        Returns:
            The created Service model instance
        """
        # Parse config if it's a string
        config = service_data.config
        if isinstance(config, str):
            config = json.loads(config)

        # Get adapter to validate engine
        adapter = self._get_adapter(service_data.engine)

        # Create service model
        service = ServiceModel(
            name=service_data.name,
            model_id=service_data.model_id,
            engine=service_data.engine,
            config=json.dumps(config) if config else None,
            status=ServiceStatus.STOPPED,
        )

        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)

        return service

    def update_service(self, service_id: int, service_data: ServiceUpdate) -> Optional[ServiceModel]:
        """Update a service instance.

        Args:
            service_id: The service ID
            service_data: The update data

        Returns:
            The updated Service model instance or None
        """
        service = self.get_service(service_id)
        if service is None:
            return None

        update_data = service_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(service, key, value)

        self.db.commit()
        self.db.refresh(service)
        return service

    def start_service(self, service_id: int) -> ServiceModel:
        """Start a service instance.

        Args:
            service_id: The service ID

        Returns:
            The updated Service model instance

        Raises:
            ValueError: If service not found or already running
            RuntimeError: If service fails to start
        """
        service = self.get_service(service_id)
        if service is None:
            raise ValueError(f"Service {service_id} not found")

        if service.status == ServiceStatus.RUNNING:
            raise ValueError(f"Service {service_id} is already running")

        # Get adapter
        adapter = self._get_adapter(service.engine)

        # Parse config
        config = json.loads(service.config) if service.config else {}

        # Get model path if model_id is set
        if service.model_id and service.model:
            model_path = service.model.path
            # Set the model path based on engine
            if service.engine == "vllm":
                config["model"] = model_path
            elif service.engine == "lmdeploy":
                config["model_path"] = model_path
            elif service.engine == "llamacpp":
                config["model"] = model_path

        # Get available port (or use specified port)
        port = config.get("port") or config.get("server_port") or self._get_available_port(adapter.get_default_port())
        config["port"] = port
        if "server_port" in config:
            config["server_port"] = port

        # Build command
        command = adapter.build_command(config)

        # Get log file path
        log_file = str(LOGS_DIR / f"service_{service_id}.log")

        # Start the process
        process_info = ProcessManager.start_process(
            command=command,
            port=port,
            service_id=service_id,
            log_file=log_file
        )

        # Wait for service to be ready
        health_url = adapter.health_check_url(port)
        ready = self._wait_for_ready(port, health_url)

        if not ready:
            # Service failed to start, cleanup
            ProcessManager.stop_process(process_info.pid, service_id)
            service.status = ServiceStatus.ERROR
            self.db.commit()
            raise RuntimeError(f"Service {service_id} failed to start within timeout")

        # Update service status
        service.status = ServiceStatus.RUNNING
        service.port = port
        service.pid = process_info.pid
        service.command = command  # Save the command
        service.started_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(service)

        return service

    def stop_service(self, service_id: int) -> ServiceModel:
        """Stop a service instance.

        Args:
            service_id: The service ID

        Returns:
            The updated Service model instance

        Raises:
            ValueError: If service not found or not running
        """
        service = self.get_service(service_id)
        if service is None:
            raise ValueError(f"Service {service_id} not found")

        if service.status != ServiceStatus.RUNNING:
            raise ValueError(f"Service {service_id} is not running")

        if service.pid is None:
            raise ValueError(f"Service {service_id} has no PID")

        # Stop the process
        success = ProcessManager.stop_process(service.pid, service_id)

        if success:
            service.status = ServiceStatus.STOPPED
            service.stopped_at = datetime.utcnow()
        else:
            service.status = ServiceStatus.ERROR

        self.db.commit()
        self.db.refresh(service)

        return service

    def restart_service(self, service_id: int) -> ServiceModel:
        """Restart a service instance.

        Args:
            service_id: The service ID

        Returns:
            The updated Service model instance
        """
        service = self.get_service(service_id)
        if service is None:
            raise ValueError(f"Service {service_id} not found")

        # Stop if running
        if service.status == ServiceStatus.RUNNING:
            self.stop_service(service_id)
            # Small delay before restart
            time.sleep(2)

        # Start the service
        return self.start_service(service_id)

    def delete_service(self, service_id: int) -> bool:
        """Delete a service instance.

        Args:
            service_id: The service ID

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If service is running
        """
        service = self.get_service(service_id)
        if service is None:
            return False

        if service.status == ServiceStatus.RUNNING:
            raise ValueError(f"Cannot delete running service {service_id}. Stop it first.")

        self.db.delete(service)
        self.db.commit()
        return True

    def get_service_status(self, service_id: int) -> Dict[str, Any]:
        """Get the detailed status of a service.

        Args:
            service_id: The service ID

        Returns:
            Dictionary with service status information
        """
        service = self.get_service(service_id)
        if service is None:
            return {"error": f"Service {service_id} not found"}

        status_info = {
            "id": service.id,
            "name": service.name,
            "engine": service.engine,
            "status": service.status,
            "port": service.port,
            "pid": service.pid,
            "running": False,
            "uptime": None,
        }

        # Check if process is actually running
        if service.pid and ProcessManager.is_process_running(service.pid):
            status_info["running"] = True
            if service.started_at:
                uptime = (datetime.utcnow() - service.started_at).total_seconds()
                status_info["uptime"] = uptime

        elif service.status == ServiceStatus.RUNNING:
            # Process should be running but isn't
            status_info["status"] = ServiceStatus.ERROR
            service.status = ServiceStatus.ERROR
            self.db.commit()

        return status_info

    def get_service_logs(self, service_id: int, lines: int = 100) -> Dict[str, Any]:
        """Get the logs for a service.

        Args:
            service_id: The service ID
            lines: Number of log lines to return

        Returns:
            Dictionary with log content
        """
        service = self.get_service(service_id)
        if service is None:
            return {"error": f"Service {service_id} not found"}

        log_file = LOGS_DIR / f"service_{service_id}.log"

        if not log_file.exists():
            return {
                "service_id": service_id,
                "logs": "",
                "message": "No log file found"
            }

        try:
            with open(log_file, 'r') as f:
                # Read last N lines
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            return {
                "service_id": service_id,
                "logs": ''.join(log_lines),
                "lines": len(log_lines),
                "total_lines": len(all_lines)
            }
        except Exception as e:
            return {
                "service_id": service_id,
                "logs": "",
                "error": str(e)
            }

    def get_service_metrics(self, service_id: int) -> Dict[str, Any]:
        """Get performance metrics for a service.

        Args:
            service_id: The service ID

        Returns:
            Dictionary with service metrics
        """
        service = self.get_service(service_id)
        if service is None:
            return {"error": f"Service {service_id} not found"}

        if service.status != ServiceStatus.RUNNING or service.port is None:
            return {
                "service_id": service_id,
                "status": service.status,
                "metrics": None,
                "message": "Service is not running"
            }

        # Get adapter for the engine
        try:
            adapter = self._get_adapter(service.engine)
        except ValueError:
            return {
                "service_id": service_id,
                "error": f"Unknown engine: {service.engine}"
            }

        # Fetch metrics from the service's metrics endpoint
        metrics_url = f"http://localhost:{service.port}/metrics"

        try:
            response = requests.get(metrics_url, timeout=10)
            if response.status_code == 200:
                metrics_text = response.text
                parsed_metrics = adapter.parse_metrics(metrics_text)
                return {
                    "service_id": service_id,
                    "port": service.port,
                    "metrics": parsed_metrics
                }
            else:
                return {
                    "service_id": service_id,
                    "error": f"Failed to fetch metrics: HTTP {response.status_code}"
                }
        except requests.RequestException as e:
            return {
                "service_id": service_id,
                "error": f"Failed to connect to service: {str(e)}"
            }

    def get_available_port(self, start_port: int = 8000, end_port: int = 9000) -> int:
        """Get an available port.

        Args:
            start_port: Starting port number
            end_port: Ending port number

        Returns:
            Available port number
        """
        return self._get_available_port(start_port, end_port)

    def get_engine_params(self, engine: str) -> Dict[str, Any]:
        """Get supported parameters for an engine.

        Args:
            engine: The engine name

        Returns:
            Dictionary with parameter definitions
        """
        adapter = self._get_adapter(engine)
        return adapter.get_supported_params()

    def get_engine_param_groups(self, engine: str) -> Dict[str, str]:
        """Get parameter groups for an engine.

        Args:
            engine: The engine name

        Returns:
            Dictionary with group names
        """
        adapter = self._get_adapter(engine)
        return adapter.get_param_groups()
