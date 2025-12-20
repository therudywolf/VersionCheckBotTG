"""Database setup and session management."""
from contextlib import contextmanager
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from config import settings

Base = declarative_base()

# Create engine with connection pooling
db_url = settings.DATABASE_URL

if db_url.startswith("sqlite:///"):
    # SQLite configuration
    db_path = db_url.replace("sqlite:///", "")
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,  # SQLite doesn't support connection pooling, use StaticPool
        pool_pre_ping=False
    )
elif db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg2://"):
    # PostgreSQL configuration with connection pooling
    engine = create_engine(
        db_url,
        echo=False,
        poolclass=pool.QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
else:
    # Default configuration for other databases
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Get database session generator.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Get database session as context manager.
    
    Usage:
        with get_db_context() as db:
            # use db
            pass
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

