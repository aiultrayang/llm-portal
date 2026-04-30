"""Pydantic schemas for Benchmark."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BenchmarkConfig(BaseModel):
    """Schema for benchmark configuration.

    Attributes:
        target_url: Target API URL for benchmarking.
        model: Model name to benchmark.
        prompt_tokens_start: Starting prompt token count.
        prompt_tokens_end: Ending prompt token count.
        prompt_tokens_step: Step size for prompt token iteration.
        concurrent: Number of concurrent requests.
        requests_per_point: Number of requests per data point.
        max_tokens: Maximum tokens to generate.
        stream: Whether to use streaming mode.
    """

    target_url: str = Field(..., description="Target API URL for benchmarking")
    model: str = Field(..., description="Model name to benchmark")
    prompt_tokens_start: int = Field(default=128, ge=1, description="Starting prompt token count")
    prompt_tokens_end: int = Field(default=2048, ge=1, description="Ending prompt token count")
    prompt_tokens_step: int = Field(default=128, ge=1, description="Step size for prompt token iteration")
    concurrent: int = Field(default=1, ge=1, description="Number of concurrent requests")
    requests_per_point: int = Field(default=10, ge=1, description="Number of requests per data point")
    max_tokens: int = Field(default=100, ge=1, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Whether to use streaming mode")


class CompareConfig(BaseModel):
    """Schema for comparison benchmark configuration.

    Attributes:
        compare_type: Type of comparison (e.g., 'engines', 'models', 'configs').
        targets: List of targets to compare.
        config: Benchmark configuration for the comparison.
    """

    compare_type: str = Field(..., description="Type of comparison", max_length=50)
    targets: List[str] = Field(..., description="List of targets to compare")
    config: BenchmarkConfig = Field(..., description="Benchmark configuration for the comparison")


class BenchmarkResultResponse(BaseModel):
    """Schema for BenchmarkResult response.

    Attributes:
        id: Unique identifier for the benchmark result.
        test_type: Type of benchmark test (e.g., 'performance', 'quality').
        config: Configuration used for the benchmark test.
        summary: Summary of the benchmark results.
        status: Current status of the benchmark.
        created_at: Timestamp when the benchmark was created.
        completed_at: Timestamp when the benchmark completed.
    """

    id: int = Field(..., description="Unique identifier for the benchmark result")
    test_type: str = Field(..., description="Type of benchmark test", max_length=100)
    config: Optional[str] = Field(default=None, description="Configuration used for the benchmark test")
    summary: Optional[str] = Field(default=None, description="Summary of the benchmark results")
    status: str = Field(default="pending", description="Current status of the benchmark", max_length=20)
    created_at: datetime = Field(..., description="Timestamp when the benchmark was created")
    completed_at: Optional[datetime] = Field(default=None, description="Timestamp when the benchmark completed")

    model_config = {"from_attributes": True}
