"""Pydantic schemas for Service."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ServiceBase(BaseModel):
    """Base schema for Service.

    Attributes:
        name: Display name of the service instance.
        model_id: Foreign key reference to the model being served.
        engine: The inference engine being used (e.g., 'llama.cpp', 'vllm').
        config: Configuration parameters for the service (JSON string).
    """

    model_config = {"protected_namespaces": ()}

    name: str = Field(..., description="Display name of the service instance", max_length=255)
    model_id: Optional[int] = Field(default=None, description="Foreign key reference to the model being served")
    engine: str = Field(default="unknown", description="The inference engine being used", max_length=100)
    config: Optional[str] = Field(default=None, description="Configuration parameters for the service")


class ServiceCreate(ServiceBase):
    """Schema for creating a new Service.

    Inherits all fields from ServiceBase.
    """

    pass


class ServiceUpdate(BaseModel):
    """Schema for updating an existing Service.

    All fields are optional to support partial updates.

    Attributes:
        name: New display name for the service instance.
        config: New configuration parameters for the service.
    """

    name: Optional[str] = Field(default=None, description="Display name of the service instance", max_length=255)
    config: Optional[str] = Field(default=None, description="Configuration parameters for the service")


class ServiceResponse(ServiceBase):
    """Schema for Service response.

    Inherits all fields from ServiceBase and adds database-generated fields.

    Attributes:
        id: Unique identifier for the service.
        status: Current status of the service.
        port: Port number the service is running on.
        pid: Process ID of the service (if applicable).
        created_at: Timestamp when the service was created.
    """

    id: int = Field(..., description="Unique identifier for the service")
    status: str = Field(default="stopped", description="Current status of the service", max_length=20)
    port: Optional[int] = Field(default=None, description="Port number the service is running on")
    pid: Optional[int] = Field(default=None, description="Process ID of the service")
    created_at: datetime = Field(..., description="Timestamp when the service was created")

    model_config = {"from_attributes": True}
