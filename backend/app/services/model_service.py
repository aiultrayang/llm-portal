"""Model management business logic service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import MODELS_DIR
from app.models.config import ModelScanPath
from app.models.model import Model
from app.schemas.model import ModelCreate


class ModelService:
    """Service for managing LLM models.

    This service handles business logic for model management including:
    - Listing and retrieving models
    - Scanning directories for model discovery
    - Adding and deleting models
    - Detecting model formats
    - Determining supported engines for each format

    Attributes:
        db: SQLAlchemy database session.
    """

    # Format to engine mapping
    FORMAT_ENGINE_MAP: Dict[str, List[str]] = {
        "safetensors": ["vllm", "lmdeploy"],
        "gguf": ["llamacpp"],
        "pytorch": ["vllm", "lmdeploy"],
    }

    def __init__(self, db: Session) -> None:
        """Initialize the ModelService.

        Args:
            db: SQLAlchemy database session for database operations.
        """
        self.db = db

    def list_models(self) -> List[Model]:
        """Get a list of all registered models.

        Returns:
            List of Model objects representing all models in the database.
        """
        return self.db.query(Model).order_by(Model.created_at.desc()).all()

    def get_model(self, model_id: int) -> Optional[Model]:
        """Get a specific model by its ID.

        Args:
            model_id: The unique identifier of the model.

        Returns:
            The Model object if found, None otherwise.
        """
        return self.db.query(Model).filter(Model.id == model_id).first()

    def _get_scan_paths(self) -> List[Path]:
        """Get all enabled model scan paths.

        Returns paths from database configuration if available,
        otherwise falls back to default MODELS_DIR.

        Returns:
            List of Path objects to scan for models.
        """
        # Get enabled paths from database
        db_paths = (
            self.db.query(ModelScanPath)
            .filter(ModelScanPath.enabled == 1)
            .all()
        )

        if db_paths:
            paths = []
            for p in db_paths:
                path = Path(p.path)
                if path.exists() and path.is_dir():
                    paths.append(path)
            return paths

        # Fallback to default directory
        if MODELS_DIR.exists():
            return [MODELS_DIR]
        return []

    def scan_models(self) -> List[Dict[str, Any]]:
        """Scan the configured model directories for available models.

        This method scans all enabled scan paths from database configuration
        (or default MODELS_DIR if none configured) and discovers model files/directories,
        detecting their format and supported engines.

        Returns:
            List of dictionaries containing discovered model information.
            Each dict contains: name, path, format, size, supported_engines.
        """
        discovered_models: List[Dict[str, Any]] = []
        seen_paths: set = set()

        scan_paths = self._get_scan_paths()
        if not scan_paths:
            return discovered_models

        for scan_path in scan_paths:
            try:
                # Scan directory contents
                for item in scan_path.iterdir():
                    # Skip already seen paths
                    item_str = str(item.resolve())
                    if item_str in seen_paths:
                        continue
                    seen_paths.add(item_str)

                    try:
                        if item.is_file():
                            # Check for GGUF files
                            if item.suffix.lower() == ".gguf":
                                model_info = self._create_model_info(item)
                                discovered_models.append(model_info)
                        elif item.is_dir():
                            # Check for safetensors or pytorch models in directory
                            format_type = self.detect_model_format(item)
                            if format_type != "unknown":
                                model_info = self._create_model_info(item)
                                discovered_models.append(model_info)
                    except (PermissionError, OSError):
                        # Skip items we can't access
                        continue
            except (PermissionError, OSError):
                # Skip directories we can't scan
                continue

        return discovered_models

    def _create_model_info(self, path: Path) -> Dict[str, Any]:
        """Create model info dictionary from a path.

        Args:
            path: Path to the model file or directory.

        Returns:
            Dictionary with model information.
        """
        format_type = self.detect_model_format(path)
        supported_engines = self.get_supported_engines(format_type)
        size = self._calculate_size(path)

        return {
            "name": path.name,
            "path": str(path.resolve()),
            "format": format_type,
            "size": size,
            "supported_engines": supported_engines,
        }

    def _calculate_size(self, path: Path) -> int:
        """Calculate the size of a model file or directory.

        Args:
            path: Path to the model file or directory.

        Returns:
            Size in bytes.
        """
        if path.is_file():
            return path.stat().st_size

        # For directories, sum all file sizes
        total_size = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass  # Skip files that can't be accessed
        return total_size

    def add_model(self, model_data: ModelCreate) -> Model:
        """Add a new model to the database.

        Args:
            model_data: Pydantic schema containing model information.

        Returns:
            The newly created Model object.
        """
        # Auto-detect format if path exists and format is 'unknown'
        path = Path(model_data.path)
        if path.exists() and model_data.format == "unknown":
            detected_format = self.detect_model_format(path)
            model_data.format = detected_format

        # Auto-determine supported engines if not provided
        if model_data.supported_engines is None:
            model_data.supported_engines = self.get_supported_engines(model_data.format)

        # Calculate size if not provided
        if model_data.size == 0 and path.exists():
            model_data.size = self._calculate_size(path)

        model = Model(
            name=model_data.name,
            path=model_data.path,
            size=model_data.size,
            format=model_data.format,
            supported_engines=model_data.supported_engines,
            metadata_json=model_data.metadata if hasattr(model_data, "metadata") else None,
        )

        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)

        return model

    def delete_model(self, model_id: int) -> bool:
        """Delete a model from the database.

        Args:
            model_id: The unique identifier of the model to delete.

        Returns:
            True if the model was deleted, False if not found.
        """
        model = self.get_model(model_id)
        if model is None:
            return False

        self.db.delete(model)
        self.db.commit()
        return True

    def detect_model_format(self, path: Path) -> str:
        """Detect the format of a model file or directory.

        Detection logic:
        - safetensors: directory contains .safetensors files
        - gguf: file extension is .gguf
        - pytorch: directory contains pytorch_model.bin or model.safetensors

        Args:
            path: Path to the model file or directory.

        Returns:
            Format string: 'safetensors', 'gguf', 'pytorch', or 'unknown'.
        """
        if path.is_file():
            # Check for GGUF file
            if path.suffix.lower() == ".gguf":
                return "gguf"
            # Check for safetensors file
            if path.suffix.lower() == ".safetensors":
                return "safetensors"
            return "unknown"

        if path.is_dir():
            # Check for safetensors files in directory
            safetensors_files = list(path.glob("*.safetensors"))
            if safetensors_files:
                return "safetensors"

            # Check for pytorch_model.bin (classic PyTorch format)
            pytorch_bin = path / "pytorch_model.bin"
            if pytorch_bin.exists():
                return "pytorch"

            # Check for model.safetensors (another safetensors naming)
            model_safetensors = path / "model.safetensors"
            if model_safetensors.exists():
                return "safetensors"

            # Check for config.json with pytorch_model.bin index
            config_json = path / "config.json"
            pytorch_index = path / "pytorch_model.bin.index.json"
            if config_json.exists() or pytorch_index.exists():
                # If there's a config.json but no safetensors, likely pytorch
                if not safetensors_files:
                    return "pytorch"

        return "unknown"

    def get_supported_engines(self, format: str) -> List[str]:
        """Get the list of supported engines for a model format.

        Args:
            format: The model format (safetensors, gguf, pytorch).

        Returns:
            List of engine names that can run this format.
            Returns empty list for unknown formats.
        """
        return self.FORMAT_ENGINE_MAP.get(format, [])