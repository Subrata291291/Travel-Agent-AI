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

connect_args = {}

# SQLite requires this setting when the application may access
# the database from different execution contexts.
if settings.database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    settings.database_url,
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