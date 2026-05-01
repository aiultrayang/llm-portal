"""Benchmark Runner Service - Performance testing for LLM services."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import BENCHMARK_DIR
from app.models.benchmark import BenchmarkResult, BenchmarkStatus
from app.schemas.benchmark import BenchmarkConfig, CompareConfig


@dataclass
class BenchmarkTask:
    """Running benchmark task information."""

    benchmark_id: str
    status: str = BenchmarkStatus.PENDING
    progress: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class MetricsResult:
    """Performance metrics from a single request."""

    # Timing metrics
    prefill_time_ms: float = 0.0
    decode_time_ms: float = 0.0
    ttft_ms: float = 0.0  # Time to first token
    tpot_ms: float = 0.0  # Time per output token
    total_time_ms: float = 0.0

    # Token counts
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Throughput
    tokens_per_second: float = 0.0

    # Request info
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prefill_time_ms": self.prefill_time_ms,
            "decode_time_ms": self.decode_time_ms,
            "ttft_ms": self.ttft_ms,
            "tpot_ms": self.tpot_ms,
            "total_time_ms": self.total_time_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tokens_per_second": self.tokens_per_second,
            "success": self.success,
            "error": self.error,
        }


class MetricsCollector:
    """Collect performance metrics from LLM responses."""

    def __init__(self):
        """Initialize the metrics collector."""
        pass

    async def collect_metrics(
        self,
        response: Dict[str, Any],
        start_time: float,
        stream: bool = False
    ) -> MetricsResult:
        """Extract performance metrics from a response.

        Args:
            response: The API response data
            start_time: Request start timestamp
            stream: Whether this was a streaming response

        Returns:
            MetricsResult with collected metrics
        """
        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000

        result = MetricsResult()
        result.total_time_ms = total_time_ms

        try:
            # Extract usage info
            usage = response.get("usage", {})
            result.prompt_tokens = usage.get("prompt_tokens", 0)
            result.completion_tokens = usage.get("completion_tokens", 0)
            result.total_tokens = usage.get("total_tokens", 0)

            # Extract timing from response metadata (if available)
            # Different engines may provide different metrics
            if "timings" in response:
                timings = response["timings"]
                result.prefill_time_ms = timings.get("prompt_processing", 0) * 1000
                result.decode_time_ms = timings.get("generation", 0) * 1000

            # For OpenAI-compatible responses, check for custom headers/fields
            if "stats" in response:
                stats = response["stats"]
                result.ttft_ms = stats.get("time_to_first_token_ms", 0)
                result.prefill_time_ms = stats.get("prefill_time_ms", result.prefill_time_ms)

            # Calculate throughput
            if result.completion_tokens > 0 and total_time_ms > 0:
                result.tokens_per_second = (result.completion_tokens / total_time_ms) * 1000

            # Calculate TPOT if we have completion tokens
            if result.completion_tokens > 0:
                result.tpot_ms = total_time_ms / result.completion_tokens
                # If we have TTFT, subtract it from total decode time
                if result.ttft_ms > 0:
                    decode_time = total_time_ms - result.ttft_ms
                    result.tpot_ms = decode_time / result.completion_tokens

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def calculate_aggregate_metrics(
        self,
        metrics_list: List[MetricsResult]
    ) -> Dict[str, Any]:
        """Calculate aggregate statistics from multiple measurements.

        Args:
            metrics_list: List of MetricsResult from multiple requests

        Returns:
            Dictionary with aggregate statistics
        """
        if not metrics_list:
            return {}

        # Filter successful results
        successful = [m for m in metrics_list if m.success]
        if not successful:
            return {
                "success_count": 0,
                "error_count": len(metrics_list),
                "errors": [m.error for m in metrics_list if m.error]
            }

        def calc_stats(values: List[float]) -> Dict[str, float]:
            """Calculate min, max, avg, p50, p95, p99."""
            if not values:
                return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

            sorted_vals = sorted(values)
            n = len(sorted_vals)

            return {
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "avg": sum(values) / n,
                "p50": sorted_vals[n // 2],
                "p95": sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[-1],
                "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[-1],
            }

        return {
            "success_count": len(successful),
            "error_count": len(metrics_list) - len(successful),
            "prompt_tokens": calc_stats([m.prompt_tokens for m in successful]),
            "completion_tokens": calc_stats([m.completion_tokens for m in successful]),
            "total_tokens": calc_stats([m.total_tokens for m in successful]),
            "ttft_ms": calc_stats([m.ttft_ms for m in successful if m.ttft_ms > 0]),
            "tpot_ms": calc_stats([m.tpot_ms for m in successful if m.tpot_ms > 0]),
            "prefill_time_ms": calc_stats([m.prefill_time_ms for m in successful if m.prefill_time_ms > 0]),
            "decode_time_ms": calc_stats([m.decode_time_ms for m in successful if m.decode_time_ms > 0]),
            "total_time_ms": calc_stats([m.total_time_ms for m in successful]),
            "tokens_per_second": calc_stats([m.tokens_per_second for m in successful if m.tokens_per_second > 0]),
        }


class BenchmarkRunner:
    """Performance test runner for LLM services."""

    # Default timeout for benchmark requests (seconds)
    DEFAULT_TIMEOUT = 120.0
    STREAM_TIMEOUT = 300.0

    # In-memory storage for running tasks
    _running_tasks: Dict[str, BenchmarkTask] = {}

    def __init__(self, db: Session):
        """Initialize the benchmark runner.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.metrics_collector = MetricsCollector()

        # Ensure benchmark results directory exists
        self.results_dir = BENCHMARK_DIR / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _generate_benchmark_id(self) -> str:
        """Generate a unique benchmark ID."""
        return f"bench_{uuid.uuid4().hex[:12]}"

    async def run_single_benchmark(
        self,
        config: BenchmarkConfig
    ) -> str:
        """Run a single model/engine benchmark test.

        Args:
            config: Benchmark configuration

        Returns:
            Benchmark ID
        """
        benchmark_id = self._generate_benchmark_id()

        # Create database record
        benchmark = BenchmarkResult(
            test_type="single",
            config=json.dumps(config.model_dump()),
            status=BenchmarkStatus.PENDING,
        )
        self.db.add(benchmark)
        self.db.commit()

        # Create task tracking
        task = BenchmarkTask(
            benchmark_id=benchmark_id,
            config=config.model_dump(),
            started_at=datetime.utcnow(),
        )
        self._running_tasks[benchmark_id] = task

        # Update benchmark ID in database
        benchmark.id = int(benchmark_id.split("_")[1], 16) % 10000000  # Generate numeric ID

        # Start background task
        asyncio.create_task(self._run_benchmark_task(benchmark_id, config))

        return benchmark_id

    async def _run_benchmark_task(
        self,
        benchmark_id: str,
        config: BenchmarkConfig
    ) -> None:
        """Execute the benchmark in background.

        Args:
            benchmark_id: Benchmark task ID
            config: Benchmark configuration
        """
        task = self._running_tasks.get(benchmark_id)
        if not task:
            return

        try:
            task.status = BenchmarkStatus.RUNNING

            # Calculate token range
            token_range = list(range(
                config.prompt_tokens_start,
                config.prompt_tokens_end + 1,
                config.prompt_tokens_step
            ))

            task.total_steps = len(token_range)
            results = []

            # Run benchmark for each token count
            for i, prompt_tokens in enumerate(token_range):
                task.current_step = f"Testing {prompt_tokens} prompt tokens"
                task.completed_steps = i

                # Run concurrent requests for this point
                point_results = await self._run_benchmark_point(
                    config, prompt_tokens
                )
                results.append({
                    "prompt_tokens": prompt_tokens,
                    "metrics": self.metrics_collector.calculate_aggregate_metrics(point_results),
                    "details": [r.to_dict() for r in point_results],
                })

                task.progress = (i + 1) / task.total_steps * 100

            # Calculate overall summary
            summary = self._calculate_summary(results)
            task.result = {
                "benchmark_id": benchmark_id,
                "config": config.model_dump(),
                "results": results,
                "summary": summary,
                "completed_at": datetime.utcnow().isoformat(),
            }

            # Save results to file
            result_file = self.results_dir / f"{benchmark_id}.json"
            with open(result_file, "w") as f:
                json.dump(task.result, f, indent=2)

            task.status = BenchmarkStatus.COMPLETED

        except Exception as e:
            task.status = BenchmarkStatus.FAILED
            task.error = str(e)

    async def _run_benchmark_point(
        self,
        config: BenchmarkConfig,
        prompt_tokens: int
    ) -> List[MetricsResult]:
        """Run benchmark for a specific token count.

        Args:
            config: Benchmark configuration
            prompt_tokens: Number of prompt tokens to test

        Returns:
            List of metrics from all requests
        """
        results = []

        # Generate prompt with approximate token count
        # Use a simple word-based approximation (roughly 0.75 words per token)
        prompt = self._generate_prompt(prompt_tokens)

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(config.concurrent)

        async def single_request(idx: int) -> MetricsResult:
            """Execute a single benchmark request."""
            async with semaphore:
                return await self._execute_request(config, prompt)

        # Run all requests
        tasks = [single_request(i) for i in range(config.requests_per_point)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to MetricsResult
        processed_results = []
        for r in results:
            if isinstance(r, Exception):
                mr = MetricsResult()
                mr.success = False
                mr.error = str(r)
                processed_results.append(mr)
            else:
                processed_results.append(r)

        return processed_results

    def _generate_prompt(self, target_tokens: int) -> str:
        """Generate a prompt with approximate token count.

        Args:
            target_tokens: Target number of tokens

        Returns:
            Generated prompt string
        """
        # Simple word repetition strategy
        # Approximate: 1 token ~ 0.75 words (English)
        word_count = int(target_tokens * 0.75)
        words = ["test"] * word_count
        return " ".join(words)

    async def _execute_request(
        self,
        config: BenchmarkConfig,
        prompt: str
    ) -> MetricsResult:
        """Execute a single benchmark request.

        Args:
            config: Benchmark configuration
            prompt: Prompt to send

        Returns:
            MetricsResult from the request
        """
        start_time = time.time()

        request_body = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": config.max_tokens,
            "stream": config.stream,
            "temperature": 0.7,
        }

        url = f"{config.target_url.rstrip('/')}/v1/chat/completions"

        try:
            if config.stream:
                return await self._execute_streaming_request(
                    config, url, request_body, start_time
                )
            else:
                return await self._execute_non_streaming_request(
                    config, url, request_body, start_time
                )
        except Exception as e:
            result = MetricsResult()
            result.success = False
            result.error = str(e)
            result.total_time_ms = (time.time() - start_time) * 1000
            return result

    async def _execute_non_streaming_request(
        self,
        config: BenchmarkConfig,
        url: str,
        request_body: Dict[str, Any],
        start_time: float
    ) -> MetricsResult:
        """Execute a non-streaming request."""
        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=request_body)
            response.raise_for_status()
            data = response.json()

            return await self.metrics_collector.collect_metrics(
                data, start_time, stream=False
            )

    async def _execute_streaming_request(
        self,
        config: BenchmarkConfig,
        url: str,
        request_body: Dict[str, Any],
        start_time: float
    ) -> MetricsResult:
        """Execute a streaming request and collect metrics."""
        first_token_time = None
        tokens_received = 0
        full_content = ""

        async with httpx.AsyncClient(timeout=self.STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST", url, json=request_body, timeout=self.STREAM_TIMEOUT
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    if first_token_time is None:
                                        first_token_time = time.time()
                                    tokens_received += 1
                                    full_content += content
                        except json.JSONDecodeError:
                            pass

        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000
        ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else 0

        result = MetricsResult()
        result.total_time_ms = total_time_ms
        result.ttft_ms = ttft_ms
        result.completion_tokens = tokens_received
        result.prompt_tokens = int(request_body.get("max_tokens", 100) * 0.75)  # Approximation

        if tokens_received > 0:
            result.tpot_ms = (total_time_ms - ttft_ms) / tokens_received if ttft_ms > 0 else total_time_ms / tokens_received
            result.tokens_per_second = (tokens_received / total_time_ms) * 1000

        result.success = True
        return result

    def _calculate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall summary from benchmark results.

        Args:
            results: List of benchmark point results

        Returns:
            Summary dictionary
        """
        if not results:
            return {}

        # Collect all metrics
        all_ttft = []
        all_tpot = []
        all_tps = []

        for point in results:
            metrics = point.get("metrics", {})
            if metrics.get("ttft_ms"):
                avg = metrics["ttft_ms"].get("avg", 0)
                if avg > 0:
                    all_ttft.append(avg)
            if metrics.get("tpot_ms"):
                avg = metrics["tpot_ms"].get("avg", 0)
                if avg > 0:
                    all_tpot.append(avg)
            if metrics.get("tokens_per_second"):
                avg = metrics["tokens_per_second"].get("avg", 0)
                if avg > 0:
                    all_tps.append(avg)

        summary = {
            "total_points": len(results),
            "token_range": {
                "min": results[0]["prompt_tokens"] if results else 0,
                "max": results[-1]["prompt_tokens"] if results else 0,
            },
        }

        if all_ttft:
            summary["avg_ttft_ms"] = sum(all_ttft) / len(all_ttft)
        if all_tpot:
            summary["avg_tpot_ms"] = sum(all_tpot) / len(all_tpot)
        if all_tps:
            summary["avg_tokens_per_second"] = sum(all_tps) / len(all_tps)

        return summary

    async def run_compare_benchmark(
        self,
        config: CompareConfig
    ) -> str:
        """Run a comparison benchmark between multiple targets.

        Args:
            config: Comparison configuration

        Returns:
            Benchmark ID
        """
        benchmark_id = self._generate_benchmark_id()

        # Create database record
        benchmark = BenchmarkResult(
            test_type=f"compare_{config.compare_type}",
            config=json.dumps(config.model_dump()),
            status=BenchmarkStatus.PENDING,
        )
        self.db.add(benchmark)
        self.db.commit()

        # Create task tracking
        task = BenchmarkTask(
            benchmark_id=benchmark_id,
            config=config.model_dump(),
            started_at=datetime.utcnow(),
        )
        self._running_tasks[benchmark_id] = task

        # Start background task
        asyncio.create_task(self._run_compare_task(benchmark_id, config))

        return benchmark_id

    async def _run_compare_task(
        self,
        benchmark_id: str,
        config: CompareConfig
    ) -> None:
        """Execute comparison benchmark in background.

        Args:
            benchmark_id: Benchmark task ID
            config: Comparison configuration
        """
        task = self._running_tasks.get(benchmark_id)
        if not task:
            return

        try:
            task.status = BenchmarkStatus.RUNNING

            results = {}
            total_targets = len(config.targets)
            task.total_steps = total_targets

            # Run benchmark for each target
            for i, target in enumerate(config.targets):
                task.current_step = f"Benchmarking {target}"
                task.completed_steps = i

                # Create config for this target
                target_config = BenchmarkConfig(
                    target_url=config.config.target_url,
                    model=target,
                    prompt_tokens_start=config.config.prompt_tokens_start,
                    prompt_tokens_end=config.config.prompt_tokens_end,
                    prompt_tokens_step=config.config.prompt_tokens_step,
                    concurrent=config.config.concurrent,
                    requests_per_point=config.config.requests_per_point,
                    max_tokens=config.config.max_tokens,
                    stream=config.config.stream,
                )

                # If compare_type is engines, modify URL instead of model
                if config.compare_type == "engines":
                    target_config.target_url = target
                    target_config.model = config.config.model

                # Run benchmark
                token_range = list(range(
                    target_config.prompt_tokens_start,
                    target_config.prompt_tokens_end + 1,
                    target_config.prompt_tokens_step
                ))

                target_results = []
                for prompt_tokens in token_range:
                    point_results = await self._run_benchmark_point(
                        target_config, prompt_tokens
                    )
                    target_results.append({
                        "prompt_tokens": prompt_tokens,
                        "metrics": self.metrics_collector.calculate_aggregate_metrics(point_results),
                    })

                results[target] = {
                    "results": target_results,
                    "summary": self._calculate_summary(target_results),
                }

                task.progress = (i + 1) / total_targets * 100

            # Calculate comparison summary
            comparison_summary = self._calculate_comparison_summary(results)

            task.result = {
                "benchmark_id": benchmark_id,
                "compare_type": config.compare_type,
                "config": config.model_dump(),
                "results": results,
                "comparison": comparison_summary,
                "completed_at": datetime.utcnow().isoformat(),
            }

            # Save results
            result_file = self.results_dir / f"{benchmark_id}.json"
            with open(result_file, "w") as f:
                json.dump(task.result, f, indent=2)

            task.status = BenchmarkStatus.COMPLETED

        except Exception as e:
            task.status = BenchmarkStatus.FAILED
            task.error = str(e)

    def _calculate_comparison_summary(
        self,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comparison summary between targets.

        Args:
            results: Results for each target

        Returns:
            Comparison summary
        """
        comparison = {
            "targets": list(results.keys()),
            "metrics_comparison": {},
        }

        # Collect metrics for comparison
        metrics_to_compare = ["avg_ttft_ms", "avg_tpot_ms", "avg_tokens_per_second"]

        for metric in metrics_to_compare:
            values = {}
            for target, data in results.items():
                summary = data.get("summary", {})
                if metric in summary:
                    values[target] = summary[metric]

            if values:
                # Find best performer
                if metric == "avg_tokens_per_second":
                    # Higher is better
                    best = max(values.items(), key=lambda x: x[1])
                else:
                    # Lower is better
                    best = min(values.items(), key=lambda x: x[1])

                comparison["metrics_comparison"][metric] = {
                    "values": values,
                    "best": best[0],
                }

        return comparison

    def get_benchmark_status(self, benchmark_id: str) -> dict:
        """Get benchmark progress status.

        Args:
            benchmark_id: Benchmark ID

        Returns:
            Status dictionary
        """
        task = self._running_tasks.get(benchmark_id)

        if task:
            return {
                "benchmark_id": benchmark_id,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "total_steps": task.total_steps,
                "completed_steps": task.completed_steps,
                "error": task.error,
                "started_at": task.started_at.isoformat() if task.started_at else None,
            }

        # Check if results exist
        result_file = self.results_dir / f"{benchmark_id}.json"
        if result_file.exists():
            return {
                "benchmark_id": benchmark_id,
                "status": BenchmarkStatus.COMPLETED,
                "progress": 100.0,
            }

        return {
            "benchmark_id": benchmark_id,
            "status": "not_found",
            "error": f"Benchmark {benchmark_id} not found",
        }

    def get_benchmark_result(self, benchmark_id: str) -> dict:
        """Get benchmark results.

        Args:
            benchmark_id: Benchmark ID

        Returns:
            Results dictionary
        """
        # Check running task first
        task = self._running_tasks.get(benchmark_id)
        if task and task.result:
            return task.result

        # Check saved results
        result_file = self.results_dir / f"{benchmark_id}.json"
        if result_file.exists():
            with open(result_file, "r") as f:
                return json.load(f)

        return {
            "benchmark_id": benchmark_id,
            "error": f"Benchmark {benchmark_id} not found",
        }

    def get_benchmark_history(self, limit: int = 20) -> List[dict]:
        """Get benchmark history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of benchmark records
        """
        history = []

        # Get from saved results
        result_files = sorted(
            self.results_dir.glob("bench_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]

        for result_file in result_files:
            try:
                with open(result_file, "r") as f:
                    data = json.load(f)

                history.append({
                    "benchmark_id": data.get("benchmark_id"),
                    "test_type": "compare" if "compare_type" in data else "single",
                    "config": data.get("config", {}),
                    "summary": data.get("summary", {}),
                    "completed_at": data.get("completed_at"),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        # Add running tasks
        for benchmark_id, task in self._running_tasks.items():
            if task.status not in [BenchmarkStatus.COMPLETED, BenchmarkStatus.FAILED]:
                history.insert(0, {
                    "benchmark_id": benchmark_id,
                    "test_type": "compare" if "compare_type" in (task.config or {}) else "single",
                    "status": task.status,
                    "progress": task.progress,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                })

        return history[:limit]

    def delete_benchmark(self, benchmark_id: str) -> bool:
        """Delete a benchmark record.

        Args:
            benchmark_id: Benchmark ID

        Returns:
            True if deleted, False if not found
        """
        # Remove from memory
        if benchmark_id in self._running_tasks:
            del self._running_tasks[benchmark_id]

        # Remove result file
        result_file = self.results_dir / f"{benchmark_id}.json"
        if result_file.exists():
            result_file.unlink()
            return True

        return False
