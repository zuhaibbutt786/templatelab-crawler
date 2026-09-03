"""SQLAlchemy ORM models matching the required schema."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side=[id], back_populates="children"
    )
    children: Mapped[List["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    templates: Mapped[List["TemplatePage"]] = relationship(
        "TemplatePage", back_populates="category"
    )


class TemplateFormat(Base):
    __tablename__ = "template_formats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class TemplatePage(Base):
    __tablename__ = "template_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    template_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    advertised_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    updated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    download_available: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="TemplateLab")
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Optional[Category]] = relationship(
        "Category", back_populates="templates"
    )
    formats: Mapped[List[TemplateFormat]] = relationship(
        "TemplateFormat",
        secondary="page_formats",
        back_populates="pages",
    )
    sections: Mapped[List["PageSection"]] = relationship(
        "PageSection", back_populates="page", cascade="all, delete-orphan"
    )
    images: Mapped[List["PageImage"]] = relationship(
        "PageImage", back_populates="page", cascade="all, delete-orphan"
    )


# Association table for many-to-many formats
class PageFormat(Base):
    __tablename__ = "page_formats"

    page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("template_pages.id", ondelete="CASCADE"), primary_key=True
    )
    format_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("template_formats.id", ondelete="CASCADE"), primary_key=True
    )


# Add backref on TemplateFormat
TemplateFormat.pages = relationship(
    "TemplatePage", secondary="page_formats", back_populates="formats"
)


class PageSection(Base):
    __tablename__ = "page_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("template_pages.id", ondelete="CASCADE"), nullable=False
    )
    heading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    page: Mapped[TemplatePage] = relationship("TemplatePage", back_populates="sections")


class PageImage(Base):
    __tablename__ = "page_images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("template_pages.id", ondelete="CASCADE"), nullable=False
    )
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alt_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    page: Mapped[TemplatePage] = relationship("TemplatePage", back_populates="images")


class RelatedPage(Base):
    __tablename__ = "related_pages"

    page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("template_pages.id", ondelete="CASCADE"), primary_key=True
    )
    related_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("template_pages.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (UniqueConstraint("page_id", "related_page_id"),)


class CrawlLog(Base):
    __tablename__ = "crawl_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
