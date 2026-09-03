"""Basic database model smoke tests (requires running Postgres)."""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Skip if no DATABASE_URL
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


def test_tables_exist():
    from app.database import init_db, engine
    init_db()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        names = {r[0] for r in result}
    for expected in (
        "categories",
        "template_pages",
        "template_formats",
        "page_formats",
        "page_sections",
        "page_images",
        "related_pages",
        "crawl_log",
    ):
        assert expected in names
