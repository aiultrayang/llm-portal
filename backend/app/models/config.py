"""System configuration model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemConfig(Base):
    """System configuration model for storing platform settings.

    This model stores key-value configuration pairs that can be
    modified at runtime through the API.
    """

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key}, value={self.value[:50]}...)>"


class ModelScanPath(Base):
    """Model scan path configuration.

    This model stores the directories that should be scanned for models.
    Multiple paths can be configured and enabled/disabled individually.
    """

    __tablename__ = "model_scan_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)  # 1=enabled, 0=disabled
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<ModelScanPath(path={self.path}, status={status})>"
