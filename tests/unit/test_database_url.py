from sqlalchemy import create_engine

from app.database.connection import resolve_database_url


def test_database_url_selects_postgresql_psycopg_dialect():
    url = resolve_database_url(
        "sqlite:///local.db",
        {"DATABASE_URL": "postgresql://user:pass@localhost/travel_agent"},
    )

    engine = create_engine(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_database_url_selects_sqlite_when_configured():
    url = resolve_database_url("sqlite:///:memory:", {})

    engine = create_engine(url)
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        engine.dispose()


def test_nonempty_database_url_environment_value_takes_precedence():
    url = resolve_database_url(
        "sqlite:///local.db",
        {"DATABASE_URL": "  postgres://user:pass@localhost/travel_agent  "},
    )

    assert url.startswith("postgresql+psycopg://")
