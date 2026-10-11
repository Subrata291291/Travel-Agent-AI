from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ---------------------------------------------------------
# Import application database metadata
# ---------------------------------------------------------
#
# Base.metadata contains all SQLAlchemy models.
#
# Importing models here is important because SQLAlchemy
# needs to know about every table before Alembic can
# compare the Python models with the database schema.
#
from app.database.connection import Base, resolve_database_url
from app.config.settings import settings
from app.database.models import (
    Tenant,
    User,
    Booking,
    HotelBooking,
    WorkflowState,
    UserMemory,
    UserMemoryEmbedding,
    ConversationMessage,
)


# ---------------------------------------------------------
# Alembic configuration
# ---------------------------------------------------------

config = context.config
database_url = resolve_database_url(settings.database_url)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


# ---------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ---------------------------------------------------------
# Target metadata
# ---------------------------------------------------------
#
# Alembic uses this metadata to compare:
#
# Python Models
#       vs
# Existing Database
#
# and generate migration operations.
#

target_metadata = Base.metadata


# ---------------------------------------------------------
# Offline migration
# ---------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations without creating a live database connection.

    Alembic generates SQL statements using the configured
    database URL.
    """

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------
# Online migration
# ---------------------------------------------------------

def run_migrations_online() -> None:
    """
    Run migrations using a live database connection.
    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
