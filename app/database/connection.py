import os
from collections.abc import Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config.settings import settings


# ============================================================
# DATABASE BASE
# ============================================================

# All SQLAlchemy models inherit from this Base.
Base = declarative_base()


# ============================================================
# DATABASE ENGINE
# ============================================================

def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs to SQLAlchemy's Psycopg 3 dialect."""
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def resolve_database_url(
    configured_url: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Prefer a non-empty DATABASE_URL, falling back to app settings."""
    environ = os.environ if environ is None else environ
    environment_url = environ.get("DATABASE_URL", "").strip()
    return normalize_database_url(environment_url or configured_url)


database_url = resolve_database_url(settings.database_url)

connect_args = {}

# SQLite requires this setting when the application may access
# the database from different execution contexts.
if database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    database_url,
    connect_args=connect_args,
    future=True,
)


# ============================================================
# DATABASE SESSION FACTORY
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Create database tables.

    Role:
    - Used during development to make sure required tables exist.
    - Production will later use Alembic migrations instead.
    """

    # Importing the model registers it with Base.metadata.
    from app.database.models import Booking  # noqa: F401

    Base.metadata.create_all(
        bind=engine
    )


# ============================================================
# DATABASE SESSION HELPER
# ============================================================

def get_db():
    """
    Provide a controlled database session.

    Role:
    - Creates a database session.
    - Rolls back if an error occurs.
    - Always closes the session.
    """

    db = SessionLocal()

    try:
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
