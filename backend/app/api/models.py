"""Model management API routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.model import ModelCreate, ModelResponse
from app.services.model_service import ModelService

router = APIRouter(prefix="/api/models", tags=["models"])


def get_model_service(db: Session = Depends(get_db)) -> ModelService:
    """Dependency injection for ModelService.

    Args:
        db: SQLAlchemy database session.

    Returns:
        ModelService instance with the database session.
    """
    return ModelService(db)


@router.get("", response_model=List[ModelResponse])
async def list_models(
    service: ModelService = Depends(get_model_service),
) -> List[ModelResponse]:
    """Get a list of all registered models.

    Args:
        service: ModelService instance.

    Returns:
        List of model information.
    """
    models = service.list_models()
    return [ModelResponse.model_validate(m) for m in models]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: int,
    service: ModelService = Depends(get_model_service),
) -> ModelResponse:
    """Get details of a specific model.

    Args:
        model_id: The unique identifier of the model.
        service: ModelService instance.

    Returns:
        Model information.

    Raises:
        HTTPException: 404 if model not found.
    """
    model = service.get_model(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id {model_id} not found",
        )
    return ModelResponse.model_validate(model)


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def add_model(
    model_data: ModelCreate,
    service: ModelService = Depends(get_model_service),
) -> ModelResponse:
    """Add a new model to the platform.

    Args:
        model_data: Model information to add.
        service: ModelService instance.

    Returns:
        The newly created model information.
    """
    model = service.add_model(model_data)
    return ModelResponse.model_validate(model)


@router.post("/scan", response_model=List[Dict[str, Any]])
async def scan_models(
    service: ModelService = Depends(get_model_service),
) -> List[Dict[str, Any]]:
    """Scan the models directory for available models.

    This endpoint scans the configured models directory and discovers
    model files/directories, automatically detecting their format and
    supported engines.

    Args:
        service: ModelService instance.

    Returns:
        List of discovered model information.
    """
    return service.scan_models()


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: int,
    service: ModelService = Depends(get_model_service),
) -> None:
    """Delete a model from the platform.

    Args:
        model_id: The unique identifier of the model to delete.
        service: ModelService instance.

    Raises:
        HTTPException: 404 if model not found.
    """
    deleted = service.delete_model(model_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id {model_id} not found",
        )