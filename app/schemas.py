"""Pydantic schemas for the FastAPI layer."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    url: Optional[str] = None


class CategoryOut(CategoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FormatOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TemplatePageBase(BaseModel):
    url: str
    title: str
    category_id: Optional[int] = None
    template_type: Optional[str] = None
    advertised_count: Optional[int] = None
    description: Optional[str] = None
    publication_date: Optional[date] = None
    updated_date: Optional[date] = None
    download_available: Optional[bool] = None
    source: str = "TemplateLab"


class TemplatePageOut(TemplatePageBase):
    id: int
    content_hash: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    formats: List[FormatOut] = Field(default_factory=list)
    category: Optional[CategoryOut] = None

    model_config = ConfigDict(from_attributes=True)


class TemplatePageList(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TemplatePageOut]


class StatsOut(BaseModel):
    total_urls_discovered: int
    total_successfully_crawled: int
    total_failed: int
    total_templates: int
    total_categories: int
    total_subcategories: int
    total_formats: int
    last_crawl_time: Optional[datetime] = None
    pages_added_today: int
    pages_updated_today: int
    http_errors: dict
    duplicate_urls: int = 0


class CrawlStatusOut(BaseModel):
    status: str
    message: str
    stats: Optional[StatsOut] = None
