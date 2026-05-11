"""Database setup and session management."""
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path
from typing import Generator
import os
import logging

from config import settings

log = logging.getLogger(__name__)

Base = declarative_base()

_engine = None
_SessionLocal = None


def _ensure_db_path_valid():
    """Ensure database path is valid and accessible."""
    db_url = settings.DATABASE_URL
    
    if not db_url.startswith("sqlite:///"):
        return db_url

    db_path = db_url.replace("sqlite:///", "")
    if not Path(db_path).is_absolute():
        db_path = str(Path(db_path).resolve())

    db_file_path = Path(db_path)
    db_dir = db_file_path.parent

    if db_file_path.exists() and db_file_path.is_dir():
        try:
            if not any(db_file_path.iterdir()):
                try:
                    db_file_path.rmdir()
                except (OSError, PermissionError):
                    alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
                    db_path = str(alt_path)
                    db_file_path = Path(db_path)
            else:
                alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
                db_path = str(alt_path)
                db_file_path = Path(db_path)
        except Exception:
            alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
            db_path = str(alt_path)
            db_file_path = Path(db_path)

    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

    if not os.access(db_dir, os.W_OK):
        raise PermissionError(f"Database directory is not writable: {db_dir}")

    if db_file_path.exists() and not os.access(db_file_path, os.W_OK):
        raise PermissionError(f"Database file is not writable: {db_path}")

    return db_path


def _get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            db_path = _ensure_db_path_valid()
            _engine = create_engine(
                f"sqlite:///{db_path}",
                echo=False,
                connect_args={"check_same_thread": False}
            )
        else:
            _engine = create_engine(db_url, echo=False)
    return _engine


def _get_session_local():
    """Get or create session local."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


engine = _get_engine()
SessionLocal = _get_session_local()


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        existing_tables = inspector.get_table_names()

        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    try:
                        table.create(bind=conn, checkfirst=True)
                    except OperationalError as e:
                        if "already exists" not in str(e).lower():
                            raise
                else:
                    existing_indexes = {idx.get("name") for idx in inspector.get_indexes(table.name) if idx.get("name")}
                    for index in table.indexes:
                        if index.name and index.name not in existing_indexes:
                            try:
                                index.create(bind=conn, checkfirst=True)
                            except OperationalError as e:
                                if "already exists" not in str(e).lower():
                                    raise
        log.info("Database tables initialized")
    except Exception as e:
        log.error(f"Error creating tables: {e}", exc_info=True)
        raise
