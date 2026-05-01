"""Tests for model management API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.model import Model
from app.services.model_service import ModelService


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


class TestModelService:
    """Tests for ModelService class."""

    def test_list_models_empty(self, db_session: Session) -> None:
        """Test listing models when database is empty."""
        service = ModelService(db_session)
        models = service.list_models()
        assert models == []

    def test_add_model(self, db_session: Session) -> None:
        """Test adding a model."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="Test-Model",
            path="/models/test-model",
            size=1000000,
            format="gguf",
            supported_engines=["llamacpp"],
        )

        model = service.add_model(model_data)

        assert model.id is not None
        assert model.name == "Test-Model"
        assert model.path == "/models/test-model"
        assert model.format == "gguf"
        assert model.supported_engines == ["llamacpp"]

    def test_get_model(self, db_session: Session) -> None:
        """Test getting a model by ID."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="Get-Test-Model",
            path="/models/get-test",
            format="safetensors",
        )
        added_model = service.add_model(model_data)

        retrieved = service.get_model(added_model.id)

        assert retrieved is not None
        assert retrieved.name == "Get-Test-Model"
        assert retrieved.format == "safetensors"

    def test_get_model_not_found(self, db_session: Session) -> None:
        """Test getting a non-existent model."""
        service = ModelService(db_session)
        retrieved = service.get_model(999)
        assert retrieved is None

    def test_delete_model(self, db_session: Session) -> None:
        """Test deleting a model."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="Delete-Test-Model",
            path="/models/delete-test",
        )
        added_model = service.add_model(model_data)

        deleted = service.delete_model(added_model.id)
        assert deleted is True

        retrieved = service.get_model(added_model.id)
        assert retrieved is None

    def test_delete_model_not_found(self, db_session: Session) -> None:
        """Test deleting a non-existent model."""
        service = ModelService(db_session)
        deleted = service.delete_model(999)
        assert deleted is False

    def test_detect_format_gguf(self, db_session: Session) -> None:
        """Test detecting GGUF format."""
        service = ModelService(db_session)
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            temp_path = Path(f.name)

        try:
            format_type = service.detect_model_format(temp_path)
            assert format_type == "gguf"
        finally:
            temp_path.unlink()

    def test_detect_format_safetensors(self, db_session: Session) -> None:
        """Test detecting safetensors format."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            safetensors_file = temp_path / "model.safetensors"
            safetensors_file.touch()

            format_type = service.detect_model_format(temp_path)
            assert format_type == "safetensors"

    def test_detect_format_pytorch(self, db_session: Session) -> None:
        """Test detecting PyTorch format."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pytorch_file = temp_path / "pytorch_model.bin"
            pytorch_file.touch()

            format_type = service.detect_model_format(temp_path)
            assert format_type == "pytorch"

    def test_detect_format_unknown(self, db_session: Session) -> None:
        """Test detecting unknown format."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            format_type = service.detect_model_format(temp_path)
            assert format_type == "unknown"

    def test_get_supported_engines_safetensors(self, db_session: Session) -> None:
        """Test getting supported engines for safetensors."""
        service = ModelService(db_session)
        engines = service.get_supported_engines("safetensors")
        assert "vllm" in engines
        assert "lmdeploy" in engines

    def test_get_supported_engines_gguf(self, db_session: Session) -> None:
        """Test getting supported engines for GGUF."""
        service = ModelService(db_session)
        engines = service.get_supported_engines("gguf")
        assert "llamacpp" in engines

    def test_get_supported_engines_pytorch(self, db_session: Session) -> None:
        """Test getting supported engines for PyTorch."""
        service = ModelService(db_session)
        engines = service.get_supported_engines("pytorch")
        assert "vllm" in engines
        assert "lmdeploy" in engines

    def test_get_supported_engines_unknown(self, db_session: Session) -> None:
        """Test getting supported engines for unknown format."""
        service = ModelService(db_session)
        engines = service.get_supported_engines("unknown")
        assert engines == []

    def test_scan_models_empty_directory(self, db_session: Session) -> None:
        """Test scanning empty models directory."""
        service = ModelService(db_session)
        with patch("app.services.model_service.MODELS_DIR", Path("/nonexistent")):
            models = service.scan_models()
            assert models == []


class TestModelAPI:
    """Tests for model API endpoints using direct service calls."""

    def test_list_models_api(self, db_session: Session) -> None:
        """Test listing models via service."""
        service = ModelService(db_session)
        models = service.list_models()
        assert models == []

    def test_add_model_api(self, db_session: Session) -> None:
        """Test adding model via service."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="API-Test-Model",
            path="/models/api-test",
            size=5000000,
            format="gguf",
            supported_engines=["llamacpp"],
        )

        model = service.add_model(model_data)

        assert model.id is not None
        assert model.name == "API-Test-Model"
        assert model.path == "/models/api-test"
        assert model.format == "gguf"

    def test_get_model_api(self, db_session: Session) -> None:
        """Test getting model via service."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="Get-API-Model",
            path="/models/get-api-test",
            format="safetensors",
        )
        added_model = service.add_model(model_data)

        retrieved = service.get_model(added_model.id)

        assert retrieved is not None
        assert retrieved.name == "Get-API-Model"
        assert retrieved.id == added_model.id

    def test_get_model_not_found_api(self, db_session: Session) -> None:
        """Test getting non-existent model via service."""
        service = ModelService(db_session)
        retrieved = service.get_model(999)
        assert retrieved is None

    def test_delete_model_api(self, db_session: Session) -> None:
        """Test deleting model via service."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        model_data = ModelCreate(
            name="Delete-API-Model",
            path="/models/delete-api-test",
        )
        added_model = service.add_model(model_data)

        deleted = service.delete_model(added_model.id)
        assert deleted is True

        retrieved = service.get_model(added_model.id)
        assert retrieved is None

    def test_delete_model_not_found_api(self, db_session: Session) -> None:
        """Test deleting non-existent model via service."""
        service = ModelService(db_session)
        deleted = service.delete_model(999)
        assert deleted is False

    def test_scan_models_api(self, db_session: Session) -> None:
        """Test scanning models via service."""
        service = ModelService(db_session)
        models = service.scan_models()
        assert isinstance(models, list)

    def test_list_models_with_data(self, db_session: Session) -> None:
        """Test listing models with existing data."""
        from app.schemas.model import ModelCreate

        service = ModelService(db_session)
        models_data = [
            ModelCreate(name="Model-A", path="/a", format="gguf"),
            ModelCreate(name="Model-B", path="/b", format="safetensors"),
        ]

        for data in models_data:
            service.add_model(data)

        models = service.list_models()

        assert len(models) == 2
        names = [m.name for m in models]
        assert "Model-A" in names
        assert "Model-B" in names


class TestModelServiceFormatDetection:
    """Tests for model format detection."""

    def test_detect_safetensors_file(self, db_session: Session) -> None:
        """Test detecting safetensors file format."""
        service = ModelService(db_session)
        with tempfile.NamedTemporaryFile(suffix=".safetensors", delete=False) as f:
            temp_path = Path(f.name)

        try:
            format_type = service.detect_model_format(temp_path)
            assert format_type == "safetensors"
        finally:
            temp_path.unlink()

    def test_detect_model_safetensors_in_dir(self, db_session: Session) -> None:
        """Test detecting model.safetensors in directory."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "model.safetensors").touch()

            format_type = service.detect_model_format(temp_path)
            assert format_type == "safetensors"

    def test_detect_config_json_implies_pytorch(self, db_session: Session) -> None:
        """Test that config.json implies pytorch when no safetensors."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "config.json").write_text("{}")

            format_type = service.detect_model_format(temp_path)
            assert format_type == "pytorch"

    def test_detect_pytorch_index(self, db_session: Session) -> None:
        """Test detecting pytorch_model.bin.index.json."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "pytorch_model.bin.index.json").write_text("{}")

            format_type = service.detect_model_format(temp_path)
            assert format_type == "pytorch"

    def test_calculate_size_file(self, db_session: Session) -> None:
        """Test calculating size of a file."""
        service = ModelService(db_session)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content for size calculation")
            temp_path = Path(f.name)

        try:
            size = service._calculate_size(temp_path)
            assert size > 0
        finally:
            temp_path.unlink()

    def test_calculate_size_directory(self, db_session: Session) -> None:
        """Test calculating size of a directory."""
        service = ModelService(db_session)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").write_text("content 1")
            (temp_path / "file2.txt").write_text("content 22")

            size = service._calculate_size(temp_path)
            assert size > 0