"""Export tables to JSON."""

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import get_db_session
from app.models import Category, TemplateFormat, TemplatePage


def _serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def export_json(output_dir: str = "exports/data") -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with get_db_session() as db:
        pages = (
            db.execute(
                select(TemplatePage).options(
                    joinedload(TemplatePage.formats),
                    joinedload(TemplatePage.category),
                )
            )
            .unique()
            .scalars()
            .all()
        )
        pages_data = []
        for p in pages:
            pages_data.append(
                {
                    "id": p.id,
                    "url": p.url,
                    "title": p.title,
                    "category_id": p.category_id,
                    "category": p.category.name if p.category else None,
                    "template_type": p.template_type,
                    "advertised_count": p.advertised_count,
                    "description": p.description,
                    "publication_date": _serialize(p.publication_date),
                    "updated_date": _serialize(p.updated_date),
                    "download_available": p.download_available,
                    "formats": [f.name for f in p.formats],
                    "first_seen_at": _serialize(p.first_seen_at),
                    "last_seen_at": _serialize(p.last_seen_at),
                }
            )
        (out / "template_pages.json").write_text(
            json.dumps(pages_data, indent=2, default=str), encoding="utf-8"
        )

        cats = db.execute(select(Category)).scalars().all()
        (out / "categories.json").write_text(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "name": c.name,
                        "parent_id": c.parent_id,
                        "url": c.url,
                    }
                    for c in cats
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

        fmts = db.execute(select(TemplateFormat)).scalars().all()
        (out / "formats.json").write_text(
            json.dumps([{"id": f.id, "name": f.name} for f in fmts], indent=2),
            encoding="utf-8",
        )

    print(f"JSON exports written to {out}/")


if __name__ == "__main__":
    export_json()
