"""Service model for managing running LLM service instances."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ServiceStatus:
    """Enum-like class for service status values."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class Service(Base):
    """Service table for managing running LLM service instances.

    Attributes:
        id: Unique identifier for the service.
        name: Display name of the service instance.
        model_id: Foreign key reference to the model being served.
        engine: The inference engine being used (e.g., 'llama.cpp', 'vllm').
        config: Configuration parameters for the service.
        status: Current status of the service.
        port: Port number the service is running on.
        pid: Process ID of the service (if applicable).
        created_at: Timestamp when the service was created.
        started_at: Timestamp when the service was started.
        stopped_at: Timestamp when the service was stopped.
    """

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("models.id"), nullable=True
    )
    engine: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    config: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ServiceStatus.STOPPED, index=True
    )
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship to Model
    model: Mapped[Optional["Model"]] = relationship("Model", backref="services")

    def __repr__(self) -> str:
        """Return a string representation of the Service."""
        return f"<Service(id={self.id}, name='{self.name}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the service to a dictionary.

        Returns:
            Dictionary representation of the service.
        """
        return {
            "id": self.id,
            "name": self.name,
            "model_id": self.model_id,
            "engine": self.engine,
            "config": self.config,
            "status": self.status,
            "port": self.port,
            "pid": self.pid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
        }

    def start(self, port: int, pid: int) -> None:
        """Mark the service as started.

        Args:
            port: Port number the service is running on.
            pid: Process ID of the service.
        """
        self.status = ServiceStatus.RUNNING
        self.port = port
        self.pid = pid
        self.started_at = datetime.utcnow()

    def stop(self) -> None:
        """Mark the service as stopped."""
        self.status = ServiceStatus.STOPPED
        self.stopped_at = datetime.utcnow()

    def set_error(self) -> None:
        """Mark the service as in error state."""
        self.status = ServiceStatus.ERROR
        self.stopped_at = datetime.utcnow()
