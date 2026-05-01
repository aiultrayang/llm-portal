"""Service Management API routes."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.service_manager import ServiceManager

router = APIRouter(prefix="/api/services", tags=["services"])


def get_service_manager(db: Session = Depends(get_db)) -> ServiceManager:
    """Dependency to get a ServiceManager instance.

    Args:
        db: Database session from dependency

    Returns:
        ServiceManager instance
    """
    return ServiceManager(db)


@router.get("", response_model=Dict[str, Any])
def list_services(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get a list of all services.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with list of services
    """
    services = manager.list_services(skip=skip, limit=limit)
    return {
        "services": [s.to_dict() for s in services],
        "total": len(services),
        "skip": skip,
        "limit": limit,
    }


@router.get("/port", response_model=Dict[str, Any])
def get_available_port(
    start_port: int = Query(8000, ge=1024, le=65535, description="Starting port number"),
    end_port: int = Query(9000, ge=1024, le=65535, description="Ending port number"),
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get an available port.

    Args:
        start_port: Starting port number for search
        end_port: Ending port number for search
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with available port number
    """
    port = manager.get_available_port(start_port, end_port)
    return {"port": port}


@router.get("/engines/{engine}/params", response_model=Dict[str, Any])
def get_engine_params(
    engine: str,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get supported parameters for an engine.

    Args:
        engine: Engine name (vllm, lmdeploy, llamacpp)
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with parameter definitions

    Raises:
        HTTPException: If engine is not supported
    """
    try:
        params = manager.get_engine_params(engine)
        groups = manager.get_engine_param_groups(engine)
        return {
            "engine": engine,
            "params": params,
            "groups": groups,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_service(
    service_data: ServiceCreate,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Create a new service instance.

    Args:
        service_data: Service creation data
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with created service data

    Raises:
        HTTPException: If creation fails
    """
    try:
        service = manager.create_service(service_data)
        return service.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{service_id}", response_model=Dict[str, Any])
def get_service(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get a service by ID.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with service data

    Raises:
        HTTPException: If service not found
    """
    service = manager.get_service(service_id)
    if service is None:
        raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
    return service.to_dict()


@router.put("/{service_id}", response_model=Dict[str, Any])
def update_service(
    service_id: int,
    service_data: ServiceUpdate,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Update a service instance.

    Args:
        service_id: Service ID
        service_data: Update data
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with updated service data

    Raises:
        HTTPException: If service not found
    """
    service = manager.update_service(service_id, service_data)
    if service is None:
        raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
    return service.to_dict()


@router.delete("/{service_id}", response_model=Dict[str, Any])
def delete_service(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Delete a service instance.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with deletion status

    Raises:
        HTTPException: If service not found or cannot be deleted
    """
    try:
        deleted = manager.delete_service(service_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Service {service_id} not found")
        return {"success": True, "message": f"Service {service_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{service_id}/start", response_model=Dict[str, Any])
def start_service(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Start a service instance.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with updated service data

    Raises:
        HTTPException: If start fails
    """
    try:
        service = manager.start_service(service_id)
        return service.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{service_id}/stop", response_model=Dict[str, Any])
def stop_service(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Stop a service instance.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with updated service data

    Raises:
        HTTPException: If stop fails
    """
    try:
        service = manager.stop_service(service_id)
        return service.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{service_id}/restart", response_model=Dict[str, Any])
def restart_service(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Restart a service instance.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with updated service data

    Raises:
        HTTPException: If restart fails
    """
    try:
        service = manager.restart_service(service_id)
        return service.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_id}/status", response_model=Dict[str, Any])
def get_service_status(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get the detailed status of a service.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with service status information

    Raises:
        HTTPException: If service not found
    """
    status = manager.get_service_status(service_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/{service_id}/logs", response_model=Dict[str, Any])
def get_service_logs(
    service_id: int,
    lines: int = Query(100, ge=1, le=10000, description="Number of log lines to return"),
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get the logs for a service.

    Args:
        service_id: Service ID
        lines: Number of log lines to return
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with log content

    Raises:
        HTTPException: If service not found
    """
    logs = manager.get_service_logs(service_id, lines)
    if "error" in logs and "not found" in logs.get("error", ""):
        raise HTTPException(status_code=404, detail=logs["error"])
    return logs


@router.get("/{service_id}/metrics", response_model=Dict[str, Any])
def get_service_metrics(
    service_id: int,
    manager: ServiceManager = Depends(get_service_manager),
) -> Dict[str, Any]:
    """Get performance metrics for a service.

    Args:
        service_id: Service ID
        manager: ServiceManager instance from dependency

    Returns:
        Dictionary with service metrics

    Raises:
        HTTPException: If service not found or metrics unavailable
    """
    metrics = manager.get_service_metrics(service_id)
    if "error" in metrics:
        raise HTTPException(status_code=400, detail=metrics["error"])
    return metrics
