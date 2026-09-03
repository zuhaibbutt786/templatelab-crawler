"""FastAPI REST endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CategoryOut,
    CrawlStatusOut,
    FormatOut,
    StatsOut,
    TemplatePageList,
    TemplatePageOut,
)
from database.repositories import (
    CategoryRepository,
    FormatRepository,
    StatsRepository,
    TemplateRepository,
)

router = APIRouter()


@router.get("/templates", response_model=TemplatePageList)
def list_templates(
    category: Optional[str] = Query(None, description="Category name filter"),
    subcategory: Optional[str] = Query(None),
    format: Optional[str] = Query(None, alias="format"),
    download_available: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cat_id = None
    if category or subcategory:
        cat_repo = CategoryRepository(db)
        name = subcategory or category
        for c in cat_repo.list_all():
            if c.name.lower() == name.lower():
                cat_id = c.id
                break

    repo = TemplateRepository(db)
    items, total = repo.list_templates(
        category_id=cat_id,
        format_name=format,
        download_available=download_available,
        search=search,
        page=page,
        limit=limit,
    )
    return TemplatePageList(
        total=total,
        page=page,
        limit=limit,
        items=[TemplatePageOut.model_validate(i) for i in items],
    )


@router.get("/templates/{id}", response_model=TemplatePageOut)
def get_template(id: int, db: Session = Depends(get_db)):
    repo = TemplateRepository(db)
    page = repo.get(id)
    if not page:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplatePageOut.model_validate(page)


@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    repo = CategoryRepository(db)
    return [CategoryOut.model_validate(c) for c in repo.list_all()]


@router.get("/categories/{id}/templates", response_model=TemplatePageList)
def templates_by_category(
    id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = TemplateRepository(db)
    items, total = repo.list_templates(category_id=id, page=page, limit=limit)
    return TemplatePageList(
        total=total,
        page=page,
        limit=limit,
        items=[TemplatePageOut.model_validate(i) for i in items],
    )


@router.get("/formats", response_model=List[FormatOut])
def list_formats(db: Session = Depends(get_db)):
    repo = FormatRepository(db)
    return [FormatOut.model_validate(f) for f in repo.list_all()]


@router.get("/search", response_model=TemplatePageList)
def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = TemplateRepository(db)
    items, total = repo.list_templates(search=q, page=page, limit=limit)
    return TemplatePageList(
        total=total,
        page=page,
        limit=limit,
        items=[TemplatePageOut.model_validate(i) for i in items],
    )


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    repo = StatsRepository(db)
    return StatsOut(**repo.get_stats())


@router.get("/crawl/status", response_model=CrawlStatusOut)
def crawl_status(db: Session = Depends(get_db)):
    repo = StatsRepository(db)
    s = repo.get_stats()
    return CrawlStatusOut(
        status="idle",
        message="Crawler runs as a separate process. Use CLI or scheduler.",
        stats=StatsOut(**s),
    )
