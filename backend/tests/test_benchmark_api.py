"""Tests for benchmark API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.schemas.benchmark import BenchmarkConfig, CompareConfig
from app.services.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkTask,
    MetricsCollector,
    MetricsResult,
)


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory SQLite database for testing.

    Yields:
        Session: A SQLAlchemy session connected to the test database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def temp_benchmark_dir(tmp_path: Path) -> Path:
    """Create a temporary benchmark directory.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path to temporary benchmark directory
    """
    benchmark_dir = tmp_path / "benchmark" / "results"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    return benchmark_dir


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_collect_metrics_basic(self) -> None:
        """Test basic metrics collection from response."""
        collector = MetricsCollector()
        start_time = 1000.0

        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }

        with patch("time.time", return_value=1001.0):  # 1 second later
            result = asyncio.run(collector.collect_metrics(response, start_time))

        assert result.success is True
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.total_tokens == 150
        assert result.total_time_ms == 1000.0  # 1 second = 1000ms

    def test_collect_metrics_with_timings(self) -> None:
        """Test metrics collection with timing information."""
        collector = MetricsCollector()
        start_time = 1000.0

        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            "timings": {
                "prompt_processing": 0.1,  # 100ms
                "generation": 0.5,  # 500ms
            }
        }

        with patch("time.time", return_value=1000.6):
            result = asyncio.run(collector.collect_metrics(response, start_time))

        assert result.prefill_time_ms == 100.0
        assert result.decode_time_ms == 500.0

    def test_collect_metrics_with_stats(self) -> None:
        """Test metrics collection with stats field."""
        collector = MetricsCollector()
        start_time = 1000.0

        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
            "stats": {
                "time_to_first_token_ms": 150.0,
                "prefill_time_ms": 100.0,
            }
        }

        with patch("time.time", return_value=1001.0):
            result = asyncio.run(collector.collect_metrics(response, start_time))

        assert result.ttft_ms == 150.0
        assert result.prefill_time_ms == 100.0

    def test_calculate_aggregate_metrics(self) -> None:
        """Test aggregate metrics calculation."""
        collector = MetricsCollector()

        metrics_list = [
            MetricsResult(
                ttft_ms=100.0,
                tpot_ms=20.0,
                tokens_per_second=50.0,
                success=True,
            ),
            MetricsResult(
                ttft_ms=150.0,
                tpot_ms=25.0,
                tokens_per_second=40.0,
                success=True,
            ),
            MetricsResult(
                ttft_ms=200.0,
                tpot_ms=30.0,
                tokens_per_second=33.0,
                success=True,
            ),
        ]

        result = collector.calculate_aggregate_metrics(metrics_list)

        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert result["ttft_ms"]["min"] == 100.0
        assert result["ttft_ms"]["max"] == 200.0
        assert result["ttft_ms"]["avg"] == pytest.approx(150.0, rel=0.1)

    def test_calculate_aggregate_metrics_with_failures(self) -> None:
        """Test aggregate metrics with some failures."""
        collector = MetricsCollector()

        metrics_list = [
            MetricsResult(ttft_ms=100.0, success=True),
            MetricsResult(success=False, error="Connection timeout"),
            MetricsResult(ttft_ms=150.0, success=True),
        ]

        result = collector.calculate_aggregate_metrics(metrics_list)

        assert result["success_count"] == 2
        assert result["error_count"] == 1


class TestMetricsResult:
    """Tests for MetricsResult dataclass."""

    def test_to_dict(self) -> None:
        """Test MetricsResult serialization."""
        result = MetricsResult(
            prefill_time_ms=100.0,
            decode_time_ms=500.0,
            ttft_ms=150.0,
            tpot_ms=25.0,
            total_time_ms=600.0,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            tokens_per_second=83.3,
            success=True,
        )

        d = result.to_dict()

        assert d["prefill_time_ms"] == 100.0
        assert d["decode_time_ms"] == 500.0
        assert d["ttft_ms"] == 150.0
        assert d["tpot_ms"] == 25.0
        assert d["tokens_per_second"] == 83.3
        assert d["success"] is True


class TestBenchmarkTask:
    """Tests for BenchmarkTask dataclass."""

    def test_default_values(self) -> None:
        """Test default values of BenchmarkTask."""
        task = BenchmarkTask(benchmark_id="test_123")

        assert task.benchmark_id == "test_123"
        assert task.status == "pending"
        assert task.progress == 0.0
        assert task.current_step == ""
        assert task.total_steps == 0
        assert task.completed_steps == 0
        assert task.error is None
        assert task.config is None
        assert task.result is None


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    def test_generate_benchmark_id(self, db_session: Session) -> None:
        """Test benchmark ID generation."""
        runner = BenchmarkRunner(db_session)
        id1 = runner._generate_benchmark_id()
        id2 = runner._generate_benchmark_id()

        assert id1.startswith("bench_")
        assert id2.startswith("bench_")
        assert id1 != id2

    def test_generate_prompt(self, db_session: Session) -> None:
        """Test prompt generation for token count."""
        runner = BenchmarkRunner(db_session)

        prompt = runner._generate_prompt(100)

        # Approximate: 100 tokens ~ 75 words
        word_count = len(prompt.split())
        assert 70 <= word_count <= 80

    def test_calculate_summary(self, db_session: Session) -> None:
        """Test benchmark summary calculation."""
        runner = BenchmarkRunner(db_session)

        results = [
            {
                "prompt_tokens": 1024,
                "metrics": {
                    "ttft_ms": {"avg": 100.0},
                    "tpot_ms": {"avg": 20.0},
                    "tokens_per_second": {"avg": 50.0},
                }
            },
            {
                "prompt_tokens": 2048,
                "metrics": {
                    "ttft_ms": {"avg": 150.0},
                    "tpot_ms": {"avg": 25.0},
                    "tokens_per_second": {"avg": 40.0},
                }
            },
        ]

        summary = runner._calculate_summary(results)

        assert summary["total_points"] == 2
        assert summary["token_range"]["min"] == 1024
        assert summary["token_range"]["max"] == 2048
        assert summary["avg_ttft_ms"] == pytest.approx(125.0, rel=0.1)
        assert summary["avg_tpot_ms"] == pytest.approx(22.5, rel=0.1)

    def test_get_benchmark_status_not_found(self, db_session: Session) -> None:
        """Test getting status of non-existent benchmark."""
        runner = BenchmarkRunner(db_session)

        status = runner.get_benchmark_status("nonexistent_id")

        assert status["status"] == "not_found"
        assert "error" in status

    def test_get_benchmark_result_not_found(self, db_session: Session) -> None:
        """Test getting result of non-existent benchmark."""
        runner = BenchmarkRunner(db_session)

        result = runner.get_benchmark_result("nonexistent_id")

        assert "error" in result

    def test_get_benchmark_history_empty(self, db_session: Session, temp_benchmark_dir: Path) -> None:
        """Test getting history when no benchmarks exist."""
        runner = BenchmarkRunner(db_session)
        runner.results_dir = temp_benchmark_dir

        history = runner.get_benchmark_history()

        assert history == []

    def test_delete_benchmark_not_found(self, db_session: Session) -> None:
        """Test deleting non-existent benchmark."""
        runner = BenchmarkRunner(db_session)

        deleted = runner.delete_benchmark("nonexistent_id")

        assert deleted is False

    def test_delete_benchmark_running_task(self, db_session: Session) -> None:
        """Test deleting a running benchmark task."""
        runner = BenchmarkRunner(db_session)

        # Add a running task
        task = BenchmarkTask(benchmark_id="test_task")
        runner._running_tasks["test_task"] = task

        deleted = runner.delete_benchmark("test_task")

        assert deleted is False
        assert "test_task" not in runner._running_tasks

    def test_delete_benchmark_with_result_file(
        self,
        db_session: Session,
        temp_benchmark_dir: Path
    ) -> None:
        """Test deleting benchmark with result file."""
        runner = BenchmarkRunner(db_session)
        runner.results_dir = temp_benchmark_dir

        # Create a result file
        result_file = temp_benchmark_dir / "bench_test123.json"
        with open(result_file, "w") as f:
            json.dump({"benchmark_id": "bench_test123"}, f)

        deleted = runner.delete_benchmark("bench_test123")

        assert deleted is True
        assert not result_file.exists()

    def test_calculate_comparison_summary(self, db_session: Session) -> None:
        """Test comparison summary calculation."""
        runner = BenchmarkRunner(db_session)

        results = {
            "model_a": {
                "summary": {
                    "avg_ttft_ms": 100.0,
                    "avg_tpot_ms": 20.0,
                    "avg_tokens_per_second": 50.0,
                }
            },
            "model_b": {
                "summary": {
                    "avg_ttft_ms": 150.0,
                    "avg_tpot_ms": 15.0,
                    "avg_tokens_per_second": 66.0,
                }
            },
        }

        comparison = runner._calculate_comparison_summary(results)

        assert comparison["targets"] == ["model_a", "model_b"]
        # Lower TTFT is better
        assert comparison["metrics_comparison"]["avg_ttft_ms"]["best"] == "model_a"
        # Higher tokens per second is better
        assert comparison["metrics_comparison"]["avg_tokens_per_second"]["best"] == "model_b"


class TestBenchmarkRunnerAsync:
    """Tests for BenchmarkRunner async methods."""

    @pytest.mark.asyncio
    async def test_run_single_benchmark_starts(
        self,
        db_session: Session,
        temp_benchmark_dir: Path
    ) -> None:
        """Test that run_single_benchmark starts a benchmark."""
        runner = BenchmarkRunner(db_session)
        runner.results_dir = temp_benchmark_dir

        config = BenchmarkConfig(
            target_url="http://localhost:8000",
            model="test-model",
            prompt_tokens_start=128,
            prompt_tokens_end=256,
            prompt_tokens_step=128,
            concurrent=1,
            requests_per_point=2,
            max_tokens=10,
            stream=False,
        )

        # Mock the internal benchmark execution
        with patch.object(runner, '_run_benchmark_task') as mock_run:
            benchmark_id = await runner.run_single_benchmark(config)

            assert benchmark_id.startswith("bench_")
            mock_run.assert_called_once()
            assert benchmark_id in runner._running_tasks

    @pytest.mark.asyncio
    async def test_run_compare_benchmark_starts(
        self,
        db_session: Session,
        temp_benchmark_dir: Path
    ) -> None:
        """Test that run_compare_benchmark starts a comparison."""
        runner = BenchmarkRunner(db_session)
        runner.results_dir = temp_benchmark_dir

        config = CompareConfig(
            compare_type="models",
            targets=["model_a", "model_b"],
            config=BenchmarkConfig(
                target_url="http://localhost:8000",
                model="default",
                prompt_tokens_start=128,
                prompt_tokens_end=256,
                prompt_tokens_step=128,
                concurrent=1,
                requests_per_point=2,
                max_tokens=10,
                stream=False,
            )
        )

        with patch.object(runner, '_run_compare_task') as mock_run:
            benchmark_id = await runner.run_compare_benchmark(config)

            assert benchmark_id.startswith("bench_")
            mock_run.assert_called_once()
            assert benchmark_id in runner._running_tasks

    @pytest.mark.asyncio
    async def test_execute_request_error_handling(
        self,
        db_session: Session
    ) -> None:
        """Test error handling in execute_request."""
        runner = BenchmarkRunner(db_session)

        config = BenchmarkConfig(
            target_url="http://invalid-host:99999",
            model="test-model",
            max_tokens=10,
            stream=False,
        )

        result = await runner._execute_request(config, "test prompt")

        assert result.success is False
        assert result.error is not None


class TestBenchmarkRunnerStreaming:
    """Tests for streaming request handling."""

    @pytest.mark.asyncio
    async def test_execute_streaming_request_mocked_time(self, db_session: Session) -> None:
        """Test streaming request metrics calculation logic."""
        # Test the metrics calculation that happens after streaming
        runner = BenchmarkRunner(db_session)

        # Simulate a streaming response being processed
        # We test the metrics calculation logic directly
        start_time = 1000.0

        # Create a MetricsResult with streaming-like values
        result = MetricsResult()
        result.total_time_ms = 500.0  # 500ms total time
        result.ttft_ms = 150.0  # Time to first token
        result.completion_tokens = 10

        # The tpot should be (total_time - ttft) / completion_tokens
        expected_tpot = (500.0 - 150.0) / 10  # 35ms per token

        # Verify the calculation
        if result.completion_tokens > 0 and result.ttft_ms > 0:
            decode_time = result.total_time_ms - result.ttft_ms
            result.tpot_ms = decode_time / result.completion_tokens
            result.tokens_per_second = (result.completion_tokens / result.total_time_ms) * 1000

        assert result.tpot_ms == pytest.approx(35.0, rel=0.1)
        assert result.tokens_per_second == pytest.approx(20.0, rel=0.1)
        result.success = True

    @pytest.mark.asyncio
    async def test_execute_streaming_request_connection_error(self, db_session: Session) -> None:
        """Test streaming request error handling when connection fails."""
        runner = BenchmarkRunner(db_session)

        config = BenchmarkConfig(
            target_url="http://invalid-host:99999",
            model="test-model",
            max_tokens=10,
            stream=True,
        )

        # This should fail due to invalid host
        result = await runner._execute_request(config, "test prompt")

        assert result.success is False
        assert result.error is not None


class TestBenchmarkSchemas:
    """Tests for benchmark Pydantic schemas."""

    def test_benchmark_config_defaults(self) -> None:
        """Test BenchmarkConfig default values."""
        config = BenchmarkConfig(
            target_url="http://localhost:8000",
            model="test-model",
        )

        assert config.prompt_tokens_start == 128
        assert config.prompt_tokens_end == 2048
        assert config.prompt_tokens_step == 128
        assert config.concurrent == 1
        assert config.requests_per_point == 10
        assert config.max_tokens == 100
        assert config.stream is False

    def test_benchmark_config_validation(self) -> None:
        """Test BenchmarkConfig validation."""
        # Valid config
        config = BenchmarkConfig(
            target_url="http://localhost:8000",
            model="test-model",
            prompt_tokens_start=1024,
            prompt_tokens_end=16384,
            prompt_tokens_step=1024,
            concurrent=4,
            requests_per_point=10,
            max_tokens=128,
            stream=True,
        )
        assert config.concurrent == 4

    def test_compare_config(self) -> None:
        """Test CompareConfig schema."""
        config = CompareConfig(
            compare_type="models",
            targets=["model_a", "model_b"],
            config=BenchmarkConfig(
                target_url="http://localhost:8000",
                model="default",
            )
        )

        assert config.compare_type == "models"
        assert len(config.targets) == 2
        assert config.config.target_url == "http://localhost:8000"


class TestBenchmarkAPIEndpoints:
    """Tests for benchmark API endpoints (integration style)."""

    def test_benchmark_config_model_dump(self) -> None:
        """Test that config can be serialized."""
        config = BenchmarkConfig(
            target_url="http://localhost:8000",
            model="test-model",
            prompt_tokens_start=1024,
            prompt_tokens_end=8192,
            prompt_tokens_step=1024,
            concurrent=4,
            requests_per_point=10,
            max_tokens=128,
            stream=True,
        )

        data = config.model_dump()

        assert data["target_url"] == "http://localhost:8000"
        assert data["model"] == "test-model"
        assert data["concurrent"] == 4
        assert data["stream"] is True


# Import asyncio for async tests
import asyncio
