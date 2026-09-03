"""Export tables to Excel workbook."""

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import get_db_session
from app.models import Category, PageFormat, TemplateFormat, TemplatePage


def export_excel(output_path: str = "exports/data/templatelab_export.xlsx") -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

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
        df_pages = pd.DataFrame(
            [
                {
                    "id": p.id,
                    "url": p.url,
                    "title": p.title,
                    "category": p.category.name if p.category else None,
                    "template_type": p.template_type,
                    "advertised_count": p.advertised_count,
                    "description": p.description,
                    "publication_date": p.publication_date,
                    "updated_date": p.updated_date,
                    "download_available": p.download_available,
                    "formats": ", ".join(f.name for f in p.formats),
                    "last_seen_at": p.last_seen_at,
                }
                for p in pages
            ]
        )

        cats = db.execute(select(Category)).scalars().all()
        df_cats = pd.DataFrame(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "parent_id": c.parent_id,
                    "url": c.url,
                }
                for c in cats
            ]
        )

        fmts = db.execute(select(TemplateFormat)).scalars().all()
        df_fmts = pd.DataFrame([{"id": f.id, "name": f.name} for f in fmts])

        pfs = db.execute(select(PageFormat)).all()
        df_pf = pd.DataFrame(
            [{"page_id": r.page_id, "format_id": r.format_id} for r in pfs]
        )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_pages.to_excel(writer, sheet_name="template_pages", index=False)
        df_cats.to_excel(writer, sheet_name="categories", index=False)
        df_fmts.to_excel(writer, sheet_name="formats", index=False)
        df_pf.to_excel(writer, sheet_name="page_formats", index=False)

    print(f"Excel export written to {path}")


if __name__ == "__main__":
    export_excel()
