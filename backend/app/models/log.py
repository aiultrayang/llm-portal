"""Log models for storing API request and response logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RequestLog(Base):
    """RequestLog table for storing incoming API request information.

    Attributes:
        id: Unique identifier for the request log.
        request_id: Unique identifier for the request (correlates with response).
        timestamp: Timestamp when the request was received.
        api_type: Type of API (e.g., 'chat', 'completion', 'embedding').
        model: Model name requested.
        service_id: Foreign key reference to the service handling the request.
        prompt_length: Length of the prompt in tokens.
        prompt_content: The actual prompt content.
        parameters: Request parameters (temperature, max_tokens, etc.).
        status: Status of the request processing.
    """

    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    api_type: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    model: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    service_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("services.id"), nullable=True
    )
    prompt_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )

    # Relationship to Service
    service: Mapped[Optional["Service"]] = relationship("Service", backref="request_logs")

    # Relationship to ResponseLog
    response: Mapped[Optional["ResponseLog"]] = relationship(
        "ResponseLog", back_populates="request", uselist=False
    )

    def __repr__(self) -> str:
        """Return a string representation of the RequestLog."""
        return f"<RequestLog(id={self.id}, request_id='{self.request_id}', model='{self.model}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the request log to a dictionary.

        Returns:
            Dictionary representation of the request log.
        """
        return {
            "id": self.id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "api_type": self.api_type,
            "model": self.model,
            "service_id": self.service_id,
            "prompt_length": self.prompt_length,
            "prompt_content": self.prompt_content,
            "parameters": self.parameters,
            "status": self.status,
        }


class ResponseLog(Base):
    """ResponseLog table for storing API response information.

    Attributes:
        id: Unique identifier for the response log.
        request_id: Foreign key reference to the request log.
        timestamp: Timestamp when the response was generated.
        status: Status of the response (success/error).
        output_length: Length of the output in tokens.
        output_content: The actual output content.
        total_time: Total time for request processing in seconds.
        prefill_time: Time for prefill phase in seconds.
        prefill_tokens: Number of tokens in prefill phase.
        decode_time: Time for decode phase in seconds.
        decode_tokens: Number of tokens in decode phase.
        ttft: Time to first token in seconds.
        tpot: Time per output token in seconds.
        gpu_util: GPU utilization percentage.
        memory_used: Memory used in GB.
    """

    __tablename__ = "response_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("request_logs.request_id"), nullable=False, unique=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    output_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_time: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    prefill_time: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    prefill_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decode_time: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    decode_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ttft: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # time to first token
    tpot: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # time per output token
    gpu_util: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    memory_used: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)

    # Relationship to RequestLog
    request: Mapped["RequestLog"] = relationship("RequestLog", back_populates="response")

    def __repr__(self) -> str:
        """Return a string representation of the ResponseLog."""
        return f"<ResponseLog(id={self.id}, request_id='{self.request_id}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response log to a dictionary.

        Returns:
            Dictionary representation of the response log.
        """
        return {
            "id": self.id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
            "output_length": self.output_length,
            "output_content": self.output_content,
            "total_time": self.total_time,
            "prefill_time": self.prefill_time,
            "prefill_tokens": self.prefill_tokens,
            "decode_time": self.decode_time,
            "decode_tokens": self.decode_tokens,
            "ttft": self.ttft,
            "tpot": self.tpot,
            "gpu_util": self.gpu_util,
            "memory_used": self.memory_used,
        }
