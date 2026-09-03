"""Export tables to CSV."""

from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.database import get_db_session
from app.models import Category, PageFormat, TemplateFormat, TemplatePage


def export_csv(output_dir: str = "exports/data") -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with get_db_session() as db:
        # template_pages
        rows = db.execute(select(TemplatePage)).scalars().all()
        pd.DataFrame(
            [
                {
                    "id": r.id,
                    "url": r.url,
                    "title": r.title,
                    "category_id": r.category_id,
                    "template_type": r.template_type,
                    "advertised_count": r.advertised_count,
                    "description": r.description,
                    "publication_date": r.publication_date,
                    "updated_date": r.updated_date,
                    "download_available": r.download_available,
                    "source": r.source,
                    "first_seen_at": r.first_seen_at,
                    "last_seen_at": r.last_seen_at,
                }
                for r in rows
            ]
        ).to_csv(out / "template_pages.csv", index=False)

        # categories
        cats = db.execute(select(Category)).scalars().all()
        pd.DataFrame(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "parent_id": c.parent_id,
                    "url": c.url,
                }
                for c in cats
            ]
        ).to_csv(out / "categories.csv", index=False)

        # formats
        fmts = db.execute(select(TemplateFormat)).scalars().all()
        pd.DataFrame([{"id": f.id, "name": f.name} for f in fmts]).to_csv(
            out / "formats.csv", index=False
        )

        # page_formats
        pfs = db.execute(select(PageFormat)).all()
        pd.DataFrame(
            [{"page_id": r.page_id, "format_id": r.format_id} for r in pfs]
        ).to_csv(out / "page_formats.csv", index=False)

    print(f"CSV exports written to {out}/")


if __name__ == "__main__":
    export_csv()
