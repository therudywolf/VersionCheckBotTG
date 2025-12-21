"""Database setup and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path
from typing import Generator
import json
import time
import os

from config import settings

Base = declarative_base()

# Debug logging setup
DEBUG_LOG_PATH = Path(".cursor/debug.log")
def debug_log(location, message, data=None, hypothesis_id=None):
    """Write debug log entry."""
    try:
        import os
        # Use absolute path to ensure it works from any directory
        abs_path = Path(__file__).parent.parent.parent / DEBUG_LOG_PATH
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id
        }
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # Log to stderr so we can see if debug logging fails
        import sys
        print(f"DEBUG LOG ERROR: {e}", file=sys.stderr)

# Global engine variable - will be initialized lazily
_engine = None
_SessionLocal = None


def _ensure_db_path_valid():
    """Ensure database path is valid and accessible."""
    db_url = settings.DATABASE_URL
    # #region agent log
    debug_log("bot/database/db.py:50", "Database URL processing", {"db_url": db_url, "is_sqlite": db_url.startswith("sqlite:///")}, "C")
    # #endregion
    
    if not db_url.startswith("sqlite:///"):
        return db_url  # Return URL for non-SQLite databases
    
    db_path = db_url.replace("sqlite:///", "")
    # Ensure absolute path for better Docker compatibility
    if not Path(db_path).is_absolute():
        # Relative path - will be resolved relative to current working directory
        # In Docker, this will be /app
        db_path = str(Path(db_path).resolve())
    
    # Ensure parent directory exists and has correct permissions
    db_file_path = Path(db_path)
    db_dir = db_file_path.parent
    
    # Check if path is a directory (Docker volume issue - if file doesn't exist, Docker creates dir)
    if db_file_path.exists() and db_file_path.is_dir():
        # #region agent log
        debug_log("bot/database/db.py:68", "Database path is a directory, not a file - attempting to fix", {"db_path": db_path}, "C")
        # #endregion
        # This can happen if Docker volume mount created a directory instead of a file
        # Try to remove the directory if it's empty, otherwise use alternative path
        try:
            # Check if directory is empty
            if not any(db_file_path.iterdir()):
                # Directory is empty, try to remove it
                # Note: This may fail if it's a volume mount, in which case we'll use alternative path
                try:
                    db_file_path.rmdir()
                    # #region agent log
                    debug_log("bot/database/db.py:77", "Removed empty directory, will create file", {"db_path": db_path}, "C")
                    # #endregion
                except (OSError, PermissionError) as e:
                    # Can't remove (likely volume mount) - use alternative path
                    alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
                    # #region agent log
                    debug_log("bot/database/db.py:83", "Could not remove directory (volume mount?), using alternative path", {"error": str(e), "original": db_path, "alternative": str(alt_path)}, "C")
                    # #endregion
                    db_path = str(alt_path)
                    db_file_path = Path(db_path)
            else:
                # Directory is not empty - use alternative path
                alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
                # #region agent log
                debug_log("bot/database/db.py:91", "Directory not empty, using alternative path", {"original": db_path, "alternative": str(alt_path)}, "C")
                # #endregion
                db_path = str(alt_path)
                db_file_path = Path(db_path)
        except Exception as e:
            # If we can't fix it, use alternative path
            alt_path = db_file_path.parent / f"{db_file_path.name}_file.db"
            # #region agent log
            debug_log("bot/database/db.py:98", "Error checking directory, using alternative path", {"error": str(e), "original": db_path, "alternative": str(alt_path)}, "C")
            # #endregion
            db_path = str(alt_path)
            db_file_path = Path(db_path)
    
    # #region agent log
    debug_log("bot/database/db.py:76", "Database path resolved", {
        "db_path": db_path, 
        "db_dir": str(db_dir),
        "db_dir_exists": db_dir.exists(),
        "db_file_exists": db_file_path.exists(),
        "is_absolute": db_file_path.is_absolute(),
        "cwd": str(Path.cwd())
    }, "C")
    # #endregion
    
    # Create parent directory if it doesn't exist
    if not db_dir.exists():
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
            # #region agent log
            debug_log("bot/database/db.py:88", "Created database directory", {"db_dir": str(db_dir)}, "C")
            # #endregion
        except Exception as e:
            # #region agent log
            debug_log("bot/database/db.py:91", "Error creating database directory", {"error": str(e), "db_dir": str(db_dir)}, "C")
            # #endregion
            raise
    
    # Ensure directory is writable
    if not os.access(db_dir, os.W_OK):
        # #region agent log
        debug_log("bot/database/db.py:97", "Database directory not writable", {"db_dir": str(db_dir)}, "C")
        # #endregion
        raise PermissionError(f"Database directory is not writable: {db_dir}")
    
    # Ensure the database file path is writable (if it exists) or the directory is writable (if it doesn't)
    if db_file_path.exists():
        if not os.access(db_file_path, os.W_OK):
            # #region agent log
            debug_log("bot/database/db.py:104", "Database file not writable", {"db_path": db_path}, "C")
            # #endregion
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
            # #region agent log
            debug_log("bot/database/db.py:120", "SQLite engine created", {"db_path": db_path}, "C")
            # #endregion
        else:
            _engine = create_engine(db_url, echo=False)
            # #region agent log
            debug_log("bot/database/db.py:124", "Non-SQLite engine created", {"db_url": db_url}, "C")
            # #endregion
    return _engine


def _get_session_local():
    """Get or create session local."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


# Initialize engine and session on module load
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
    # #region agent log
    debug_log("bot/database/db.py:194", "init_db() entry", {"engine_exists": engine is not None}, "C")
    # #endregion
    try:
        # Use checkfirst=True to avoid errors if tables/indexes already exist
        Base.metadata.create_all(bind=engine, checkfirst=True)
        # #region agent log
        debug_log("bot/database/db.py:200", "Database tables created", {}, "C")
        # #endregion
    except Exception as e:
        # #region agent log
        debug_log("bot/database/db.py:203", "Error creating tables", {"error": str(e)}, "C")
        # #endregion
        raise

