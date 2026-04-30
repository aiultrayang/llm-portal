"""Pydantic schemas for Request and Response Logs."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RequestLogBase(BaseModel):
    """Base schema for RequestLog.

    Attributes:
        request_id: Unique identifier for the request (correlates with response).
        api_type: Type of API (e.g., 'chat', 'completion', 'embedding').
        model: Model name requested.
        service_id: Foreign key reference to the service handling the request.
        prompt_length: Length of the prompt in tokens.
        prompt_content: The actual prompt content.
        parameters: Request parameters (temperature, max_tokens, etc.).
        status: Status of the request processing.
    """

    request_id: str = Field(..., description="Unique identifier for the request", max_length=64)
    api_type: str = Field(default="chat", description="Type of API", max_length=50)
    model: str = Field(..., description="Model name requested", max_length=255)
    service_id: Optional[int] = Field(default=None, description="Foreign key reference to the service handling the request")
    prompt_length: int = Field(default=0, ge=0, description="Length of the prompt in tokens")
    prompt_content: Optional[str] = Field(default=None, description="The actual prompt content")
    parameters: Optional[str] = Field(default=None, description="Request parameters (temperature, max_tokens, etc.)")
    status: str = Field(default="pending", description="Status of the request processing", max_length=20)


class RequestLogResponse(RequestLogBase):
    """Schema for RequestLog response.

    Inherits all fields from RequestLogBase and adds database-generated fields.

    Attributes:
        id: Unique identifier for the request log.
        timestamp: Timestamp when the request was received.
    """

    id: int = Field(..., description="Unique identifier for the request log")
    timestamp: datetime = Field(..., description="Timestamp when the request was received")

    model_config = {"from_attributes": True}


class ResponseLogBase(BaseModel):
    """Base schema for ResponseLog.

    Attributes:
        request_id: Foreign key reference to the request log.
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

    request_id: str = Field(..., description="Foreign key reference to the request log", max_length=64)
    status: str = Field(default="success", description="Status of the response", max_length=20)
    output_length: int = Field(default=0, ge=0, description="Length of the output in tokens")
    output_content: Optional[str] = Field(default=None, description="The actual output content")
    total_time: Optional[float] = Field(default=None, ge=0, description="Total time for request processing in seconds")
    prefill_time: Optional[float] = Field(default=None, ge=0, description="Time for prefill phase in seconds")
    prefill_tokens: Optional[int] = Field(default=None, ge=0, description="Number of tokens in prefill phase")
    decode_time: Optional[float] = Field(default=None, ge=0, description="Time for decode phase in seconds")
    decode_tokens: Optional[int] = Field(default=None, ge=0, description="Number of tokens in decode phase")
    ttft: Optional[float] = Field(default=None, ge=0, description="Time to first token in seconds")
    tpot: Optional[float] = Field(default=None, ge=0, description="Time per output token in seconds")
    gpu_util: Optional[float] = Field(default=None, ge=0, le=100, description="GPU utilization percentage")
    memory_used: Optional[float] = Field(default=None, ge=0, description="Memory used in GB")


class ResponseLogResponse(ResponseLogBase):
    """Schema for ResponseLog response.

    Inherits all fields from ResponseLogBase and adds database-generated fields.

    Attributes:
        id: Unique identifier for the response log.
        timestamp: Timestamp when the response was generated.
    """

    id: int = Field(..., description="Unique identifier for the response log")
    timestamp: datetime = Field(..., description="Timestamp when the response was generated")

    model_config = {"from_attributes": True}
