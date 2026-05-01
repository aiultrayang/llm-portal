"""System configuration API routes."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.config import ModelScanPath, SystemConfig

router = APIRouter(prefix="/api/config", tags=["config"])


# ================== Pydantic Schemas ==================

class PathItem(BaseModel):
    """Directory or file item for browsing."""
    path: str
    name: str
    is_dir: bool
    size: Optional[int] = None
    is_model: bool = False  # Whether this looks like a model directory


class DirectoryBrowseResponse(BaseModel):
    """Response for directory browsing."""
    current_path: str
    parent_path: Optional[str]
    items: List[PathItem]


class ScanPathCreate(BaseModel):
    """Schema for creating a scan path."""
    path: str
    description: Optional[str] = None


class ScanPathResponse(BaseModel):
    """Schema for scan path response."""
    id: int
    path: str
    enabled: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    """Schema for updating configuration."""
    value: str


# ================== Directory Browsing ==================

@router.get("/browse", response_model=DirectoryBrowseResponse)
async def browse_directory(
    path: str = "/",
    show_files: bool = False,
) -> DirectoryBrowseResponse:
    """Browse server directory structure.

    This endpoint allows browsing the server's file system to select
    model directories. Only directories are returned by default for safety.

    Args:
        path: The directory path to browse. Defaults to root "/".
        show_files: Whether to also show files (not just directories).

    Returns:
        Directory listing with parent path and items.

    Raises:
        HTTPException: 400 if path doesn't exist or isn't a directory.
        HTTPException: 403 if path is not accessible.
    """
    try:
        dir_path = Path(path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid path: {str(e)}"
        )

    # Security check: resolve to absolute path
    try:
        dir_path = dir_path.resolve()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve path: {str(e)}"
        )

    # Check if path exists and is a directory
    if not dir_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path does not exist: {path}"
        )

    if not dir_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {path}"
        )

    # Check if directory is readable
    if not os.access(dir_path, os.R_OK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {path}"
        )

    # Build response
    items: List[PathItem] = []

    try:
        for item in dir_path.iterdir():
            # Skip hidden files/directories
            if item.name.startswith('.'):
                continue

            try:
                is_dir = item.is_dir()
                is_file = item.is_file()

                # Skip files unless show_files is True
                if is_file and not show_files:
                    continue

                # Check if this looks like a model directory
                is_model = False
                if is_dir:
                    # Check for common model indicators
                    model_indicators = [
                        item / "config.json",
                        item / "model.safetensors",
                        item / "pytorch_model.bin",
                    ]
                    is_model = any(p.exists() for p in model_indicators)
                    # Also check for GGUF files
                    if not is_model:
                        is_model = any(f.suffix.lower() == '.gguf' for f in item.iterdir() if f.is_file())

                # For directories, also check if it's a symlink we can follow
                if is_dir and item.is_symlink():
                    try:
                        # Check if symlink target is accessible
                        target = item.resolve()
                        if not target.exists():
                            continue  # Skip broken symlinks
                    except (OSError, RuntimeError):
                        continue  # Skip inaccessible symlinks

                items.append(PathItem(
                    path=str(item),
                    name=item.name,
                    is_dir=is_dir,
                    size=item.stat().st_size if is_file else None,
                    is_model=is_model,
                ))
            except (PermissionError, OSError):
                # Skip items we can't access
                continue

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied reading directory: {path}"
        )

    # Sort: directories first, then by name
    items.sort(key=lambda x: (not x.is_dir, x.name.lower()))

    # Determine parent path
    parent_path = None
    if dir_path.parent != dir_path:  # Not root
        parent_path = str(dir_path.parent)

    return DirectoryBrowseResponse(
        current_path=str(dir_path),
        parent_path=parent_path,
        items=items,
    )


# ================== Model Scan Paths ==================

@router.get("/scan-paths", response_model=List[ScanPathResponse])
async def list_scan_paths(
    db: Session = Depends(get_db),
) -> List[ScanPathResponse]:
    """Get all configured model scan paths.

    Returns:
        List of scan path configurations.
    """
    paths = db.query(ModelScanPath).order_by(ModelScanPath.created_at).all()
    return [
        ScanPathResponse(
            id=p.id,
            path=p.path,
            enabled=bool(p.enabled),
            description=p.description,
        )
        for p in paths
    ]


@router.post("/scan-paths", response_model=ScanPathResponse, status_code=status.HTTP_201_CREATED)
async def add_scan_path(
    path_data: ScanPathCreate,
    db: Session = Depends(get_db),
) -> ScanPathResponse:
    """Add a new model scan path.

    Args:
        path_data: The path configuration to add.
        db: Database session.

    Returns:
        The created scan path.

    Raises:
        HTTPException: 400 if path doesn't exist or already added.
    """
    # Validate path exists
    path = Path(path_data.path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path does not exist: {path_data.path}"
        )
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {path_data.path}"
        )

    # Check if path already exists
    existing = db.query(ModelScanPath).filter(ModelScanPath.path == path_data.path).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path already configured: {path_data.path}"
        )

    # Add new path
    scan_path = ModelScanPath(
        path=path_data.path,
        enabled=1,
        description=path_data.description,
    )
    db.add(scan_path)
    db.commit()
    db.refresh(scan_path)

    return ScanPathResponse(
        id=scan_path.id,
        path=scan_path.path,
        enabled=bool(scan_path.enabled),
        description=scan_path.description,
    )


@router.delete("/scan-paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan_path(
    path_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a model scan path.

    Args:
        path_id: The ID of the scan path to delete.
        db: Database session.

    Raises:
        HTTPException: 404 if path not found.
    """
    scan_path = db.query(ModelScanPath).filter(ModelScanPath.id == path_id).first()
    if not scan_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan path with id {path_id} not found"
        )

    db.delete(scan_path)
    db.commit()


@router.patch("/scan-paths/{path_id}/toggle", response_model=ScanPathResponse)
async def toggle_scan_path(
    path_id: int,
    db: Session = Depends(get_db),
) -> ScanPathResponse:
    """Toggle a scan path enabled/disabled.

    Args:
        path_id: The ID of the scan path to toggle.
        db: Database session.

    Returns:
        Updated scan path configuration.

    Raises:
        HTTPException: 404 if path not found.
    """
    scan_path = db.query(ModelScanPath).filter(ModelScanPath.id == path_id).first()
    if not scan_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan path with id {path_id} not found"
        )

    scan_path.enabled = 0 if scan_path.enabled else 1
    db.commit()
    db.refresh(scan_path)

    return ScanPathResponse(
        id=scan_path.id,
        path=scan_path.path,
        enabled=bool(scan_path.enabled),
        description=scan_path.description,
    )


# ================== System Config ==================

@router.get("/{key}")
async def get_config(
    key: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a configuration value by key.

    Args:
        key: The configuration key.
        db: Database session.

    Returns:
        Configuration value.

    Raises:
        HTTPException: 404 if key not found.
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration key '{key}' not found"
        )

    return {"key": config.key, "value": config.value, "description": config.description}


@router.put("/{key}")
async def set_config(
    key: str,
    config_data: ConfigUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Set or update a configuration value.

    Args:
        key: The configuration key.
        config_data: The new value.
        db: Database session.

    Returns:
        Updated configuration.
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config:
        config.value = config_data.value
    else:
        config = SystemConfig(key=key, value=config_data.value)
        db.add(config)

    db.commit()
    db.refresh(config)

    return {"key": config.key, "value": config.value, "description": config.description}
