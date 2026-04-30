"""Benchmark model for storing benchmark test results."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BenchmarkStatus:
    """Enum-like class for benchmark status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkResult(Base):
    """BenchmarkResult table for storing benchmark test results.

    Attributes:
        id: Unique identifier for the benchmark result.
        test_type: Type of benchmark test (e.g., 'performance', 'quality').
        config: Configuration used for the benchmark test.
        summary: Summary of the benchmark results.
        status: Current status of the benchmark.
        created_at: Timestamp when the benchmark was created.
        completed_at: Timestamp when the benchmark completed.
    """

    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    config: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BenchmarkStatus.PENDING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        """Return a string representation of the BenchmarkResult."""
        return f"<BenchmarkResult(id={self.id}, test_type='{self.test_type}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the benchmark result to a dictionary.

        Returns:
            Dictionary representation of the benchmark result.
        """
        return {
            "id": self.id,
            "test_type": self.test_type,
            "config": self.config,
            "summary": self.summary,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }

    def complete(self, summary: Dict[str, Any]) -> None:
        """Mark the benchmark as completed.

        Args:
            summary: Summary of benchmark results.
        """
        self.status = BenchmarkStatus.COMPLETED
        self.summary = json.dumps(summary) if summary else None
        self.completed_at = datetime.utcnow()

    def fail(self) -> None:
        """Mark the benchmark as failed."""
        self.status = BenchmarkStatus.FAILED
        self.completed_at = datetime.utcnow()
