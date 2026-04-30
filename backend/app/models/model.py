"""Model model for storing LLM model information."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Model(Base):
    """Model table for storing LLM model metadata.

    Attributes:
        id: Unique identifier for the model.
        name: Display name of the model.
        path: File system path to the model files.
        size: Size of the model in bytes.
        format: Format of the model (e.g., 'gguf', 'safetensors', 'pytorch').
        supported_engines: List of engines that can run this model.
        metadata_json: Additional metadata about the model.
        created_at: Timestamp when the model was added to the platform.
    """

    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    format: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    supported_engines: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        """Return a string representation of the Model."""
        return f"<Model(id={self.id}, name='{self.name}', format='{self.format}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary.

        Returns:
            Dictionary representation of the model.
        """
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "format": self.format,
            "supported_engines": self.supported_engines or [],
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
