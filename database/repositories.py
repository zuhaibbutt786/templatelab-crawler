"""Data access layer – upserts, queries, stats."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Category,
    CrawlLog,
    PageFormat,
    PageImage,
    PageSection,
    RelatedPage,
    TemplateFormat,
    TemplatePage,
)
from crawler.normalizer import content_hash, normalize_format


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(
        self, name: str, url: Optional[str] = None, parent_id: Optional[int] = None
    ) -> Category:
        q = select(Category).where(Category.name == name)
        if parent_id is not None:
            q = q.where(Category.parent_id == parent_id)
        else:
            q = q.where(Category.parent_id.is_(None))
        existing = self.db.execute(q).scalar_one_or_none()
        if existing:
            if url and not existing.url:
                existing.url = url
                existing.updated_at = datetime.utcnow()
            return existing
        cat = Category(name=name, url=url, parent_id=parent_id)
        self.db.add(cat)
        self.db.flush()
        return cat

    def list_all(self) -> List[Category]:
        return list(self.db.execute(select(Category).order_by(Category.name)).scalars())

    def get(self, category_id: int) -> Optional[Category]:
        return self.db.get(Category, category_id)


class FormatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, name: str) -> TemplateFormat:
        canonical = normalize_format(name)
        existing = self.db.execute(
            select(TemplateFormat).where(TemplateFormat.name == canonical)
        ).scalar_one_or_none()
        if existing:
            return existing
        fmt = TemplateFormat(name=canonical)
        self.db.add(fmt)
        self.db.flush()
        return fmt

    def list_all(self) -> List[TemplateFormat]:
        return list(self.db.execute(select(TemplateFormat).order_by(TemplateFormat.name)).scalars())


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_url(self, url: str) -> Optional[TemplatePage]:
        return self.db.execute(
            select(TemplatePage).where(TemplatePage.url == url)
        ).scalar_one_or_none()

    def should_skip(self, url: str, interval_hours: int, force: bool = False) -> bool:
        if force:
            return False
        page = self.get_by_url(url)
        if not page or not page.last_seen_at:
            return False
        age = datetime.utcnow() - page.last_seen_at.replace(tzinfo=None)
        return age < timedelta(hours=interval_hours)

    def upsert_from_parsed(
        self,
        data: Dict[str, Any],
        category_id: Optional[int] = None,
    ) -> tuple[TemplatePage, bool]:
        """
        Insert or update a template page.
        Returns (page, created: bool).
        """
        url = data["url"]
        existing = self.get_by_url(url)

        hash_input = (data.get("title") or "") + "|" + (data.get("description") or "")
        new_hash = content_hash(hash_input)

        if existing:
            # Update
            existing.title = data.get("title") or existing.title
            existing.description = data.get("description") or existing.description
            existing.advertised_count = data.get("advertised_count")
            existing.publication_date = data.get("publication_date") or existing.publication_date
            existing.updated_date = data.get("updated_date") or existing.updated_date
            existing.download_available = data.get("download_available")
            existing.template_type = data.get("template_type") or existing.template_type
            existing.content_hash = new_hash
            existing.last_seen_at = datetime.utcnow()
            if category_id:
                existing.category_id = category_id
            page = existing
            created = False
        else:
            page = TemplatePage(
                url=url,
                title=data.get("title") or url,
                category_id=category_id,
                template_type=data.get("template_type"),
                advertised_count=data.get("advertised_count"),
                description=data.get("description"),
                publication_date=data.get("publication_date"),
                updated_date=data.get("updated_date"),
                download_available=data.get("download_available"),
                content_hash=new_hash,
            )
            self.db.add(page)
            self.db.flush()
            created = True

        # Formats
        fmt_repo = FormatRepository(self.db)
        # Clear existing links then re-add (simple approach)
        self.db.execute(
            PageFormat.__table__.delete().where(PageFormat.page_id == page.id)
        )
        for fname in data.get("formats") or []:
            fmt = fmt_repo.get_or_create(fname)
            self.db.merge(PageFormat(page_id=page.id, format_id=fmt.id))

        # Sections
        self.db.execute(
            PageSection.__table__.delete().where(PageSection.page_id == page.id)
        )
        for h in data.get("headings") or []:
            self.db.add(
                PageSection(
                    page_id=page.id,
                    heading=h.get("heading"),
                    position=h.get("position"),
                )
            )

        # Images
        self.db.execute(
            PageImage.__table__.delete().where(PageImage.page_id == page.id)
        )
        for img in data.get("images") or []:
            self.db.add(
                PageImage(
                    page_id=page.id,
                    image_url=img.get("image_url"),
                    alt_text=img.get("alt_text"),
                    position=img.get("position"),
                )
            )

        self.db.flush()
        return page, created

    def list_templates(
        self,
        category_id: Optional[int] = None,
        format_name: Optional[str] = None,
        download_available: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[TemplatePage], int]:
        q = select(TemplatePage).options(
            joinedload(TemplatePage.formats),
            joinedload(TemplatePage.category),
        )
        count_q = select(func.count(TemplatePage.id))

        if category_id is not None:
            q = q.where(TemplatePage.category_id == category_id)
            count_q = count_q.where(TemplatePage.category_id == category_id)

        if download_available is not None:
            q = q.where(TemplatePage.download_available == download_available)
            count_q = count_q.where(TemplatePage.download_available == download_available)

        if format_name:
            q = q.join(TemplatePage.formats).where(
                TemplateFormat.name.ilike(f"%{format_name}%")
            )
            count_q = count_q.join(TemplatePage.formats).where(
                TemplateFormat.name.ilike(f"%{format_name}%")
            )

        if search:
            # Use FTS if available, fallback to ILIKE
            ts_query = func.plainto_tsquery("english", search)
            fts = func.to_tsvector(
                "english",
                func.coalesce(TemplatePage.title, "")
                + " "
                + func.coalesce(TemplatePage.description, ""),
            )
            q = q.where(
                or_(
                    fts.op("@@")(ts_query),
                    TemplatePage.title.ilike(f"%{search}%"),
                    TemplatePage.description.ilike(f"%{search}%"),
                )
            )
            count_q = count_q.where(
                or_(
                    fts.op("@@")(ts_query),
                    TemplatePage.title.ilike(f"%{search}%"),
                    TemplatePage.description.ilike(f"%{search}%"),
                )
            )

        total = self.db.execute(count_q).scalar() or 0
        q = q.order_by(TemplatePage.last_seen_at.desc()).offset((page - 1) * limit).limit(limit)
        items = list(self.db.execute(q).unique().scalars())
        return items, total

    def get(self, page_id: int) -> Optional[TemplatePage]:
        return self.db.execute(
            select(TemplatePage)
            .options(
                joinedload(TemplatePage.formats),
                joinedload(TemplatePage.category),
            )
            .where(TemplatePage.id == page_id)
        ).unique().scalar_one_or_none()


class CrawlLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        url: str,
        status_code: Optional[int] = None,
        status: str = "ok",
        error_message: Optional[str] = None,
    ) -> None:
        entry = CrawlLog(
            url=url,
            status_code=status_code,
            status=status,
            error_message=error_message[:1000] if error_message else None,
        )
        self.db.add(entry)
        self.db.flush()


class StatsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_stats(self) -> Dict[str, Any]:
        total_templates = self.db.execute(select(func.count(TemplatePage.id))).scalar() or 0
        total_categories = self.db.execute(
            select(func.count(Category.id)).where(Category.parent_id.is_(None))
        ).scalar() or 0
        total_subcategories = self.db.execute(
            select(func.count(Category.id)).where(Category.parent_id.isnot(None))
        ).scalar() or 0
        total_formats = self.db.execute(select(func.count(TemplateFormat.id))).scalar() or 0

        success = (
            self.db.execute(
                select(func.count(CrawlLog.id)).where(CrawlLog.status == "ok")
            ).scalar()
            or 0
        )
        failed = (
            self.db.execute(
                select(func.count(CrawlLog.id)).where(CrawlLog.status != "ok")
            ).scalar()
            or 0
        )
        total_discovered = success + failed

        last_crawl = self.db.execute(
            select(func.max(CrawlLog.crawled_at))
        ).scalar()

        today = date.today()
        added_today = (
            self.db.execute(
                select(func.count(TemplatePage.id)).where(
                    func.date(TemplatePage.first_seen_at) == today
                )
            ).scalar()
            or 0
        )
        updated_today = (
            self.db.execute(
                select(func.count(TemplatePage.id)).where(
                    func.date(TemplatePage.last_seen_at) == today
                )
            ).scalar()
            or 0
        )

        # HTTP error breakdown
        error_rows = self.db.execute(
            select(CrawlLog.status_code, func.count(CrawlLog.id))
            .where(CrawlLog.status_code.isnot(None), CrawlLog.status != "ok")
            .group_by(CrawlLog.status_code)
        ).all()
        http_errors = {str(code): cnt for code, cnt in error_rows}

        return {
            "total_urls_discovered": total_discovered,
            "total_successfully_crawled": success,
            "total_failed": failed,
            "total_templates": total_templates,
            "total_categories": total_categories,
            "total_subcategories": total_subcategories,
            "total_formats": total_formats,
            "last_crawl_time": last_crawl,
            "pages_added_today": added_today,
            "pages_updated_today": updated_today,
            "http_errors": http_errors,
            "duplicate_urls": 0,
        }
