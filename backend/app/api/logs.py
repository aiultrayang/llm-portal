"""Log management API routes."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.log import RequestLogResponse, ResponseLogResponse
from app.services.log_service import LogService

router = APIRouter(prefix="/api/logs", tags=["logs"])


def get_log_service(db: Session = Depends(get_db)) -> LogService:
    """Dependency injection for LogService.

    Args:
        db: SQLAlchemy database session.

    Returns:
        LogService instance with the database session.
    """
    return LogService(db)


@router.get("/requests", response_model=List[RequestLogResponse])
async def get_request_logs(
    start_time: Optional[datetime] = Query(None, description="Filter by start time"),
    end_time: Optional[datetime] = Query(None, description="Filter by end time"),
    model: Optional[str] = Query(None, description="Filter by model name"),
    service_id: Optional[int] = Query(None, description="Filter by service ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: LogService = Depends(get_log_service),
) -> List[RequestLogResponse]:
    """Get request logs with optional filters.

    Args:
        start_time: Filter by start time.
        end_time: Filter by end time.
        model: Filter by model name.
        service_id: Filter by service ID.
        status: Filter by status.
        limit: Maximum number of results.
        offset: Number of results to skip.
        service: LogService instance.

    Returns:
        List of request logs matching the filters.
    """
    logs = service.query_logs(
        log_type="request",
        start_time=start_time,
        end_time=end_time,
        model=model,
        service_id=service_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [RequestLogResponse.model_validate(log) for log in logs]


@router.get("/responses", response_model=List[ResponseLogResponse])
async def get_response_logs(
    start_time: Optional[datetime] = Query(None, description="Filter by start time"),
    end_time: Optional[datetime] = Query(None, description="Filter by end time"),
    model: Optional[str] = Query(None, description="Filter by model name"),
    service_id: Optional[int] = Query(None, description="Filter by service ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: LogService = Depends(get_log_service),
) -> List[ResponseLogResponse]:
    """Get response logs with optional filters.

    Args:
        start_time: Filter by start time.
        end_time: Filter by end time.
        model: Filter by model name.
        service_id: Filter by service ID.
        status: Filter by status.
        limit: Maximum number of results.
        offset: Number of results to skip.
        service: LogService instance.

    Returns:
        List of response logs matching the filters.
    """
    logs = service.query_logs(
        log_type="response",
        start_time=start_time,
        end_time=end_time,
        model=model,
        service_id=service_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [ResponseLogResponse.model_validate(log) for log in logs]


@router.get("/stats", response_model=Dict[str, Any])
async def get_log_stats(
    start_time: Optional[datetime] = Query(None, description="Filter by start time"),
    end_time: Optional[datetime] = Query(None, description="Filter by end time"),
    group_by: str = Query("model", description="Group statistics by (model, service, api_type)"),
    service: LogService = Depends(get_log_service),
) -> Dict[str, Any]:
    """Get statistical analysis of logs.

    Args:
        start_time: Filter by start time.
        end_time: Filter by end time.
        group_by: Field to group statistics by (model, service, api_type).
        service: LogService instance.

    Returns:
        Dictionary containing log statistics:
            - total_requests: Total number of requests
            - success_rate: Percentage of successful requests
            - avg_response_time: Average total response time
            - avg_ttft: Average time to first token
            - avg_tpot: Average time per output token
            - avg_gpu_util: Average GPU utilization
            - grouped_stats: Statistics grouped by specified field
    """
    # Validate group_by value
    valid_group_by = ["model", "service", "api_type"]
    if group_by not in valid_group_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid group_by value. Must be one of: {valid_group_by}",
        )

    return service.get_log_stats(
        start_time=start_time,
        end_time=end_time,
        group_by=group_by,
    )


@router.get("/export")
async def export_logs(
    format: str = Query("json", description="Export format (json or csv)"),
    start_time: Optional[datetime] = Query(None, description="Filter by start time"),
    end_time: Optional[datetime] = Query(None, description="Filter by end time"),
    log_type: str = Query("request", description="Type of logs to export (request or response)"),
    service: LogService = Depends(get_log_service),
) -> Response:
    """Export logs in JSON or CSV format.

    Args:
        format: Export format (json or csv).
        start_time: Filter by start time.
        end_time: Filter by end time.
        log_type: Type of logs to export (request or response).
        service: LogService instance.

    Returns:
        Response containing exported log data.

    Raises:
        HTTPException: 400 if format or log_type is invalid.
    """
    # Validate format
    valid_formats = ["json", "csv"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {valid_formats}",
        )

    # Validate log_type
    valid_log_types = ["request", "response"]
    if log_type not in valid_log_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log_type. Must be one of: {valid_log_types}",
        )

    exported_data = service.export_logs(
        format=format,
        start_time=start_time,
        end_time=end_time,
        log_type=log_type,
    )

    if format == "json":
        return Response(
            content=exported_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={log_type}_logs.json"
            },
        )
    else:
        return PlainTextResponse(
            content=exported_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={log_type}_logs.csv"
            },
        )


@router.delete("", status_code=status.HTTP_200_OK)
async def cleanup_logs(
    before_date: datetime = Query(..., description="Delete logs older than this date"),
    service: LogService = Depends(get_log_service),
) -> Dict[str, Any]:
    """Clean up old logs.

    Args:
        before_date: Delete logs older than this date (ISO 8601 format).
        service: LogService instance.

    Returns:
        Dictionary containing the number of deleted entries.

    Raises:
        HTTPException: 400 if before_date is in the future.
    """
    # Validate that before_date is not in the future
    if before_date > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="before_date cannot be in the future",
        )

    deleted_count = service.cleanup_logs(before_date)

    return {
        "deleted_count": deleted_count,
        "before_date": before_date.isoformat(),
        "message": f"Successfully deleted {deleted_count} log entries",
    }


@router.get("/models", response_model=List[str])
async def get_log_models(
    service: LogService = Depends(get_log_service),
) -> List[str]:
    """Get list of distinct model names from logs.

    Args:
        service: LogService instance.

    Returns:
        List of unique model names found in logs.
    """
    return service.get_models()


@router.get("/api-types", response_model=List[str])
async def get_log_api_types(
    service: LogService = Depends(get_log_service),
) -> List[str]:
    """Get list of distinct API types from logs.

    Args:
        service: LogService instance.

    Returns:
        List of unique API types found in logs.
    """
    return service.get_api_types()


@router.get("/statuses", response_model=List[str])
async def get_log_statuses(
    service: LogService = Depends(get_log_service),
) -> List[str]:
    """Get list of distinct statuses from logs.

    Args:
        service: LogService instance.

    Returns:
        List of unique statuses found in logs.
    """
    return service.get_statuses()


@router.get("/{request_id}", response_model=Dict[str, Any])
async def get_log_detail(
    request_id: str,
    service: LogService = Depends(get_log_service),
) -> Dict[str, Any]:
    """Get complete log details for a specific request.

    Args:
        request_id: The unique request identifier.
        service: LogService instance.

    Returns:
        Dictionary containing both request and response log details.

    Raises:
        HTTPException: 404 if request log not found.
    """
    log_detail = service.get_log_detail(request_id)
    if log_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request log with id '{request_id}' not found",
        )
    return log_detail