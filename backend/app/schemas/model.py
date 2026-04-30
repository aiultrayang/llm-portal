"""Pydantic schemas for Model."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ModelBase(BaseModel):
    """Base schema for Model.

    Attributes:
        name: Display name of the model.
        path: File system path to the model files.
        size: Size of the model in bytes.
        format: Format of the model (e.g., 'gguf', 'safetensors', 'pytorch').
        supported_engines: List of engines that can run this model.
    """

    name: str = Field(..., description="Display name of the model", max_length=255)
    path: str = Field(..., description="File system path to the model files", max_length=1024)
    size: int = Field(default=0, ge=0, description="Size of the model in bytes")
    format: str = Field(default="unknown", description="Format of the model", max_length=50)
    supported_engines: Optional[List[str]] = Field(
        default=None, description="List of engines that can run this model"
    )


class ModelCreate(ModelBase):
    """Schema for creating a new Model.

    Inherits all fields from ModelBase and optionally includes an id
    for cases where the id needs to be specified during creation.
    """

    id: Optional[int] = Field(default=None, description="Optional ID for the model")


class ModelResponse(ModelBase):
    """Schema for Model response.

    Inherits all fields from ModelBase and adds database-generated fields.

    Attributes:
        id: Unique identifier for the model.
        created_at: Timestamp when the model was added to the platform.
    """

    id: int = Field(..., description="Unique identifier for the model")
    created_at: datetime = Field(..., description="Timestamp when the model was created")

    model_config = {"from_attributes": True}
