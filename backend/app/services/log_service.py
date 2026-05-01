"""Log management business logic service."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.log import RequestLog, ResponseLog


class LogService:
    """Service for managing API request and response logs.

    This service handles business logic for log management including:
    - Creating request and response logs
    - Querying logs with filters
    - Getting detailed log information
    - Statistical analysis of logs
    - Exporting logs in various formats
    - Cleaning up old logs

    Attributes:
        db: SQLAlchemy database session.
    """

    def __init__(self, db: Session) -> None:
        """Initialize the LogService.

        Args:
            db: SQLAlchemy database session for database operations.
        """
        self.db = db

    def create_request_log(
        self,
        request_id: str,
        api_type: str,
        model: str,
        service_id: int,
        prompt_length: int,
        prompt_content: str,
        parameters: dict,
        status: str = "pending"
    ) -> RequestLog:
        """Create a request log entry.

        Args:
            request_id: Unique identifier for the request.
            api_type: Type of API (e.g., 'chat', 'completion', 'embedding').
            model: Model name requested.
            service_id: ID of the service handling the request.
            prompt_length: Length of the prompt in tokens.
            prompt_content: The actual prompt content.
            parameters: Request parameters (temperature, max_tokens, etc.).
            status: Status of the request processing.

        Returns:
            The created RequestLog object.
        """
        parameters_str = json.dumps(parameters) if parameters else None

        log = RequestLog(
            request_id=request_id,
            api_type=api_type,
            model=model,
            service_id=service_id,
            prompt_length=prompt_length,
            prompt_content=prompt_content,
            parameters=parameters_str,
            status=status,
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    def generate_request_id(self) -> str:
        """Generate a unique request ID.

        Returns:
            A unique request ID string.
        """
        return uuid4().hex

    def create_response_log(
        self,
        request_id: str,
        status: str,
        output_length: int,
        output_content: str,
        total_time: float,
        prefill_time: float,
        prefill_tokens: int,
        decode_time: float,
        decode_tokens: int,
        ttft: float,
        tpot: float,
        gpu_util: float,
        memory_used: int
    ) -> ResponseLog:
        """Create a response log entry.

        Args:
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
            memory_used: Memory used in MB.

        Returns:
            The created ResponseLog object.
        """
        log = ResponseLog(
            request_id=request_id,
            status=status,
            output_length=output_length,
            output_content=output_content,
            total_time=total_time,
            prefill_time=prefill_time,
            prefill_tokens=prefill_tokens,
            decode_time=decode_time,
            decode_tokens=decode_tokens,
            ttft=ttft,
            tpot=tpot,
            gpu_util=gpu_util,
            memory_used=memory_used,
        )

        self.db.add(log)

        # Update request status
        request_log = self.db.query(RequestLog).filter(
            RequestLog.request_id == request_id
        ).first()
        if request_log:
            request_log.status = status

        self.db.commit()
        self.db.refresh(log)

        return log

    def query_logs(
        self,
        log_type: str,
        start_time: datetime = None,
        end_time: datetime = None,
        model: str = None,
        service_id: int = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Union[RequestLog, ResponseLog]]:
        """Query logs with filters.

        Args:
            log_type: Type of logs to query ('request' or 'response').
            start_time: Filter by start time.
            end_time: Filter by end time.
            model: Filter by model name.
            service_id: Filter by service ID.
            status: Filter by status.
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            List of log entries matching the filters.
        """
        if log_type == "request":
            query = self.db.query(RequestLog)
            query = query.order_by(desc(RequestLog.timestamp))

            if start_time:
                query = query.filter(RequestLog.timestamp >= start_time)
            if end_time:
                query = query.filter(RequestLog.timestamp <= end_time)
            if model:
                query = query.filter(RequestLog.model == model)
            if service_id:
                query = query.filter(RequestLog.service_id == service_id)
            if status:
                query = query.filter(RequestLog.status == status)

        elif log_type == "response":
            query = self.db.query(ResponseLog)
            query = query.order_by(desc(ResponseLog.timestamp))

            if start_time:
                query = query.filter(ResponseLog.timestamp >= start_time)
            if end_time:
                query = query.filter(ResponseLog.timestamp <= end_time)
            if status:
                query = query.filter(ResponseLog.status == status)

            # Join with RequestLog for model and service_id filters
            if model or service_id:
                query = query.join(RequestLog, ResponseLog.request_id == RequestLog.request_id)
                if model:
                    query = query.filter(RequestLog.model == model)
                if service_id:
                    query = query.filter(RequestLog.service_id == service_id)
        else:
            return []

        return query.offset(offset).limit(limit).all()

    def get_log_detail(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get complete log details (request + response) for a request ID.

        Args:
            request_id: The unique request identifier.

        Returns:
            Dictionary containing both request and response log details,
            or None if request not found.
        """
        request_log = self.db.query(RequestLog).filter(
            RequestLog.request_id == request_id
        ).first()

        if not request_log:
            return None

        response_log = self.db.query(ResponseLog).filter(
            ResponseLog.request_id == request_id
        ).first()

        result = {
            "request": request_log.to_dict(),
            "response": response_log.to_dict() if response_log else None,
        }

        return result

    def get_log_stats(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        group_by: str = "model"
    ) -> Dict[str, Any]:
        """Get statistical analysis of logs.

        Args:
            start_time: Filter by start time.
            end_time: Filter by end time.
            group_by: Group statistics by ('model', 'service', or 'api_type').

        Returns:
            Dictionary containing:
                - total_requests: Total number of requests
                - success_rate: Percentage of successful requests
                - avg_response_time: Average total response time
                - avg_ttft: Average time to first token
                - avg_tpot: Average time per output token
                - avg_gpu_util: Average GPU utilization
                - grouped_stats: Statistics grouped by specified field
        """
        # Base query for request logs
        request_query = self.db.query(RequestLog)
        if start_time:
            request_query = request_query.filter(RequestLog.timestamp >= start_time)
        if end_time:
            request_query = request_query.filter(RequestLog.timestamp <= end_time)

        total_requests = request_query.count()

        if total_requests == 0:
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "avg_ttft": 0.0,
                "avg_tpot": 0.0,
                "avg_gpu_util": 0.0,
                "grouped_stats": [],
            }

        # Count successful requests
        success_count = request_query.filter(RequestLog.status == "success").count()
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0.0

        # Join with response logs for performance metrics
        response_query = self.db.query(ResponseLog).join(
            RequestLog, ResponseLog.request_id == RequestLog.request_id
        )

        if start_time:
            response_query = response_query.filter(RequestLog.timestamp >= start_time)
        if end_time:
            response_query = response_query.filter(RequestLog.timestamp <= end_time)

        # Calculate averages
        avg_response_time = response_query.with_entities(
            func.avg(ResponseLog.total_time)
        ).scalar() or 0.0

        avg_ttft = response_query.with_entities(
            func.avg(ResponseLog.ttft)
        ).scalar() or 0.0

        avg_tpot = response_query.with_entities(
            func.avg(ResponseLog.tpot)
        ).scalar() or 0.0

        avg_gpu_util = response_query.with_entities(
            func.avg(ResponseLog.gpu_util)
        ).scalar() or 0.0

        # Group statistics
        grouped_stats = self._get_grouped_stats(
            start_time, end_time, group_by
        )

        return {
            "total_requests": total_requests,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response_time or 0, 4),
            "avg_ttft": round(avg_ttft or 0, 4),
            "avg_tpot": round(avg_tpot or 0, 4),
            "avg_gpu_util": round(avg_gpu_util or 0, 2),
            "grouped_stats": grouped_stats,
        }

    def _get_grouped_stats(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        group_by: str = "model"
    ) -> List[Dict[str, Any]]:
        """Get statistics grouped by a specific field.

        Args:
            start_time: Filter by start time.
            end_time: Filter by end time.
            group_by: Field to group by ('model', 'service', or 'api_type').

        Returns:
            List of dictionaries containing grouped statistics.
        """
        if group_by == "model":
            group_field = RequestLog.model
        elif group_by == "service":
            group_field = RequestLog.service_id
        elif group_by == "api_type":
            group_field = RequestLog.api_type
        else:
            group_field = RequestLog.model

        # Build query
        query = self.db.query(
            group_field.label("group_key"),
            func.count(RequestLog.id).label("count"),
        )

        if start_time:
            query = query.filter(RequestLog.timestamp >= start_time)
        if end_time:
            query = query.filter(RequestLog.timestamp <= end_time)

        query = query.group_by(group_field).order_by(desc("count"))

        results = []
        for row in query.all():
            results.append({
                "key": str(row.group_key) if row.group_key else "unknown",
                "count": row.count,
            })

        return results

    def export_logs(
        self,
        format: str,
        start_time: datetime = None,
        end_time: datetime = None,
        log_type: str = "request"
    ) -> str:
        """Export logs to a specific format.

        Args:
            format: Export format ('json' or 'csv').
            start_time: Filter by start time.
            end_time: Filter by end time.
            log_type: Type of logs to export ('request' or 'response').

        Returns:
            String containing the exported data.
        """
        logs = self.query_logs(
            log_type=log_type,
            start_time=start_time,
            end_time=end_time,
            limit=10000  # Limit export size
        )

        if format == "json":
            return self._export_as_json(logs)
        elif format == "csv":
            return self._export_as_csv(logs, log_type)
        else:
            return self._export_as_json(logs)

    def _export_as_json(self, logs: List[Union[RequestLog, ResponseLog]]) -> str:
        """Export logs as JSON string.

        Args:
            logs: List of log entries to export.

        Returns:
            JSON string of the logs.
        """
        data = [log.to_dict() for log in logs]
        return json.dumps(data, indent=2, default=str)

    def _export_as_csv(self, logs: List[Union[RequestLog, ResponseLog]], log_type: str) -> str:
        """Export logs as CSV string.

        Args:
            logs: List of log entries to export.
            log_type: Type of logs ('request' or 'response').

        Returns:
            CSV string of the logs.
        """
        if not logs:
            return ""

        output = io.StringIO()
        log_dict = logs[0].to_dict()
        fieldnames = list(log_dict.keys())

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for log in logs:
            row = log.to_dict()
            # Convert datetime to string for CSV
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()
            writer.writerow(row)

        return output.getvalue()

    def cleanup_logs(self, before_date: datetime) -> int:
        """Clean up old logs.

        Args:
            before_date: Delete logs older than this date.

        Returns:
            Number of log entries deleted.
        """
        # First, delete response logs for requests to be deleted
        # Get request IDs to delete
        request_ids_to_delete = self.db.query(RequestLog.request_id).filter(
            RequestLog.timestamp < before_date
        ).all()

        request_ids = [rid[0] for rid in request_ids_to_delete]

        # Delete corresponding response logs
        response_count = 0
        if request_ids:
            response_count = self.db.query(ResponseLog).filter(
                ResponseLog.request_id.in_(request_ids)
            ).delete(synchronize_session=False)

        # Delete request logs
        request_count = self.db.query(RequestLog).filter(
            RequestLog.timestamp < before_date
        ).delete(synchronize_session=False)

        self.db.commit()

        return request_count + response_count

    def get_models(self) -> List[str]:
        """Get list of distinct model names from logs.

        Returns:
            List of unique model names.
        """
        results = self.db.query(RequestLog.model).distinct().all()
        return [r[0] for r in results if r[0]]

    def get_api_types(self) -> List[str]:
        """Get list of distinct API types from logs.

        Returns:
            List of unique API types.
        """
        results = self.db.query(RequestLog.api_type).distinct().all()
        return [r[0] for r in results if r[0]]

    def get_statuses(self) -> List[str]:
        """Get list of distinct statuses from logs.

        Returns:
            List of unique statuses.
        """
        request_statuses = self.db.query(RequestLog.status).distinct().all()
        return [r[0] for r in request_statuses if r[0]]
