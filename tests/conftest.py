import os

import pytest


@pytest.fixture
def db_conn():
    """Postgres real y vacío. Se omite si no hay TEST_DATABASE_URL (¡se borra el esquema!)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida")
    from core.db import apply_migrations, connect

    conn = connect(url)
    conn.execute("drop schema public cascade; create schema public")
    apply_migrations(conn)
    yield conn
    conn.close()
