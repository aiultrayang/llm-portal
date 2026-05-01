"""Benchmark API Routes - Performance testing endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.benchmark import (
    BenchmarkConfig,
    BenchmarkResultResponse,
    CompareConfig,
)
from app.services.benchmark_runner import BenchmarkRunner


# Router
router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


def get_benchmark_runner(db: Session = Depends(get_db)) -> BenchmarkRunner:
    """Get benchmark runner instance.

    Args:
        db: Database session

    Returns:
        BenchmarkRunner instance
    """
    return BenchmarkRunner(db)


@router.post("/single")
async def run_single_benchmark(
    config: BenchmarkConfig,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Run a single model/engine performance benchmark.

    This endpoint initiates a benchmark test for a single model or engine.
    The test runs asynchronously and returns a benchmark ID for tracking.

    Args:
        config: Benchmark configuration including:
            - target_url: Target API URL
            - model: Model name to test
            - prompt_tokens_start/end/step: Token range configuration
            - concurrent: Number of concurrent requests
            - requests_per_point: Requests per data point
            - max_tokens: Maximum output tokens
            - stream: Use streaming mode

    Returns:
        Dictionary containing benchmark_id for tracking progress

    Example:
        ```json
        {
            "target_url": "http://localhost:8000",
            "model": "qwen-7b",
            "prompt_tokens_start": 1024,
            "prompt_tokens_end": 8192,
            "prompt_tokens_step": 1024,
            "concurrent": 4,
            "requests_per_point": 10,
            "max_tokens": 128,
            "stream": true
        }
        ```
    """
    try:
        benchmark_id = await runner.run_single_benchmark(config)
        return {
            "benchmark_id": benchmark_id,
            "status": "started",
            "message": "Benchmark started successfully. Use the benchmark_id to check status.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start benchmark: {str(e)}"
        )


@router.post("/compare")
async def run_compare_benchmark(
    config: CompareConfig,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Run a comparison benchmark between multiple targets.

    Supports comparing:
    - Different models on the same engine
    - Same model on different engines
    - Different configurations

    Args:
        config: Comparison configuration including:
            - compare_type: 'models' or 'engines'
            - targets: List of targets to compare
            - config: Benchmark configuration

    Returns:
        Dictionary containing benchmark_id for tracking progress

    Example:
        ```json
        {
            "compare_type": "models",
            "targets": ["qwen-7b", "llama-7b"],
            "config": {
                "target_url": "http://localhost:8000",
                "model": "default",
                "concurrent": 4,
                "requests_per_point": 10
            }
        }
        ```
    """
    # Validate compare_type
    valid_types = ["models", "engines", "configs"]
    if config.compare_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid compare_type. Must be one of: {valid_types}"
        )

    # Validate targets
    if len(config.targets) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 targets are required for comparison"
        )

    try:
        benchmark_id = await runner.run_compare_benchmark(config)
        return {
            "benchmark_id": benchmark_id,
            "status": "started",
            "compare_type": config.compare_type,
            "targets": config.targets,
            "message": "Comparison benchmark started successfully.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start comparison benchmark: {str(e)}"
        )


@router.get("/{benchmark_id}/status")
async def get_benchmark_status(
    benchmark_id: str,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Get the progress status of a running benchmark.

    Args:
        benchmark_id: The benchmark ID returned from start endpoint

    Returns:
        Status dictionary containing:
            - status: Current status (pending/running/completed/failed)
            - progress: Percentage complete (0-100)
            - current_step: Description of current step
            - total_steps: Total number of steps
            - completed_steps: Number of completed steps
            - error: Error message if failed
    """
    status = runner.get_benchmark_status(benchmark_id)

    if status.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark {benchmark_id} not found"
        )

    return status


@router.get("/{benchmark_id}/result")
async def get_benchmark_result(
    benchmark_id: str,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Get the results of a completed benchmark.

    Args:
        benchmark_id: The benchmark ID returned from start endpoint

    Returns:
        Complete benchmark results including:
            - benchmark_id: Unique identifier
            - config: Original configuration
            - results: Per-token-point metrics
            - summary: Aggregate statistics
            - comparison: Comparison data (for comparison benchmarks)
    """
    result = runner.get_benchmark_result(benchmark_id)

    if "error" in result:
        raise HTTPException(
            status_code=404,
            detail=result["error"]
        )

    return result


@router.get("/history")
async def get_benchmark_history(
    limit: int = 20,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Get history of benchmark runs.

    Args:
        limit: Maximum number of records to return (default: 20)

    Returns:
        List of benchmark records with:
            - benchmark_id: Unique identifier
            - test_type: Type of test
            - config: Test configuration
            - summary: Result summary
            - status/progress for running tests
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    history = runner.get_benchmark_history(limit)
    return {
        "count": len(history),
        "limit": limit,
        "history": history,
    }


@router.delete("/{benchmark_id}")
async def delete_benchmark(
    benchmark_id: str,
    runner: BenchmarkRunner = Depends(get_benchmark_runner)
):
    """Delete a benchmark record.

    Args:
        benchmark_id: The benchmark ID to delete

    Returns:
        Status message confirming deletion

    Raises:
        404: If benchmark not found
    """
    deleted = runner.delete_benchmark(benchmark_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark {benchmark_id} not found"
        )

    return {
        "status": "success",
        "message": f"Benchmark {benchmark_id} deleted successfully",
        "benchmark_id": benchmark_id,
    }


@router.get("/health")
async def benchmark_health():
    """Health check endpoint for benchmark service.

    Returns:
        Health status of the benchmark service
    """
    return {
        "status": "healthy",
        "service": "benchmark",
        "features": [
            "single_benchmark",
            "compare_benchmark",
            "streaming_support",
            "metrics_collection"
        ]
    }
