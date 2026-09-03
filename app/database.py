"""SQLAlchemy engine and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for scripts / crawler."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and indexes."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Full-text search index (PostgreSQL)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_template_pages_fts
                ON template_pages
                USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
                """
            )
        )
        # Additional helpful indexes (idempotent)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_tp_category_id ON template_pages (category_id);",
            "CREATE INDEX IF NOT EXISTS idx_tp_publication_date ON template_pages (publication_date);",
            "CREATE INDEX IF NOT EXISTS idx_tp_updated_date ON template_pages (updated_date);",
            "CREATE INDEX IF NOT EXISTS idx_tp_download_available ON template_pages (download_available);",
            "CREATE INDEX IF NOT EXISTS idx_tp_last_seen_at ON template_pages (last_seen_at);",
            "CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories (parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_crawl_log_crawled_at ON crawl_log (crawled_at);",
        ]:
            conn.execute(text(stmt))
        conn.commit()
    print("Database initialized (tables + indexes).")
