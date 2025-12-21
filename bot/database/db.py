"""Database setup and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path
from typing import Generator

from config import settings

Base = declarative_base()

# Create engine - using SQLite for now
# Convert sqlite:/// to sqlite:/// for proper path handling
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    # Ensure absolute path for better Docker compatibility
    if not Path(db_path).is_absolute():
        # Relative path - will be resolved relative to current working directory
        # In Docker, this will be /app
        db_path = str(Path(db_path).resolve())
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(db_url, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

