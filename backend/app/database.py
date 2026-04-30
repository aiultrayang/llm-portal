"""SQLAlchemy database connection and session management."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import DATABASE_URL

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base: Any = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session.

    Yields:
        Session: A SQLAlchemy database session.

    Example:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize the database by creating all tables.

    This should be called once when the application starts.
    """
    # Import all models to ensure they are registered
    from app.models import model, service, benchmark, log  # noqa: F401

    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all database tables.

    This is useful for testing and development.
    """
    Base.metadata.drop_all(bind=engine)
