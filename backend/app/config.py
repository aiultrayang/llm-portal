"""Configuration management for the local LLM deployment platform."""

from pathlib import Path

# Base directory (project root)
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# Backend directory
BACKEND_DIR: Path = BASE_DIR / "backend"

# Data directories
DATA_DIR: Path = BASE_DIR / "data"
DATABASE_DIR: Path = BASE_DIR / "database"
MODELS_DIR: Path = BASE_DIR / "models"
LOGS_DIR: Path = BASE_DIR / "logs"
BENCHMARK_DIR: Path = BASE_DIR / "benchmark"

# Database configuration
DATABASE_URL: str = f"sqlite:///{DATABASE_DIR / 'llm_platform.db'}"

# API configuration
API_HOST: str = "0.0.0.0"
API_PORT: int = 8000
API_RELOAD: bool = True

# CORS settings
CORS_ORIGINS: list = ["*"]
CORS_ALLOW_CREDENTIALS: bool = True
CORS_ALLOW_METHODS: list = ["*"]
CORS_ALLOW_HEADERS: list = ["*"]


def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    directories = [
        DATA_DIR,
        DATABASE_DIR,
        MODELS_DIR,
        LOGS_DIR,
        BENCHMARK_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# Ensure directories exist on module import
ensure_directories()
