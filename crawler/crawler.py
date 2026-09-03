"""Main crawler orchestration – discovery + metadata extraction + DB upsert."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx

from app.config import get_settings
from app.database import get_db_session, init_db
from crawler.discovery import Discovery
from crawler.normalizer import normalize_url
from crawler.parser import parse_template_page
from crawler.rate_limiter import RateLimiter
from database.repositories import (
    CategoryRepository,
    CrawlLogRepository,
    StatsRepository,
    TemplateRepository,
)


class CrawlerStats:
    def __init__(self):
        self.urls_discovered = 0
        self.new_pages = 0
        self.updated_pages = 0
        self.successfully_crawled = 0
        self.failed = 0
        self.skipped = 0
        self.categories = 0
        self.subcategories = 0
        self.templates = 0
        self.formats = 0
        self.start_time = time.monotonic()

    def duration(self) -> float:
        return time.monotonic() - self.start_time

    def print_summary(self) -> None:
        print("\n========== CRAWL SUMMARY ==========")
        print(f"Total URLs discovered: {self.urls_discovered}")
        print(f"New pages:             {self.new_pages}")
        print(f"Updated pages:         {self.updated_pages}")
        print(f"Successfully crawled:  {self.successfully_crawled}")
        print(f"Failed:                {self.failed}")
        print(f"Skipped:               {self.skipped}")
        print(f"Categories:            {self.categories}")
        print(f"Subcategories:         {self.subcategories}")
        print(f"Templates:             {self.templates}")
        print(f"Formats:               {self.formats}")
        print(f"Crawl duration:        {self.duration():.1f}s")
        print("===================================\n")


class TemplateLabCrawler:
    def __init__(self):
        self.settings = get_settings()
        self.limiter = RateLimiter()
        self.stats = CrawlerStats()
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=self.settings.request_timeout,
            follow_redirects=True,
            http2=True,
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def run(self, max_pages: Optional[int] = None) -> CrawlerStats:
        """Full crawl cycle: discover → extract → upsert."""
        init_db()
        assert self.client is not None

        discovery = Discovery(self.client, self.limiter)
        print("Step 1: Discovering site structure (respecting robots.txt)…")
        discovered = await discovery.discover_all()

        categories = discovered.get("categories") or []
        template_urls = discovered.get("template_urls") or []
        self.stats.urls_discovered = len(template_urls) + len(categories)

        # Persist categories
        with get_db_session() as db:
            cat_repo = CategoryRepository(db)
            for cat in categories:
                cat_repo.get_or_create(name=cat["name"], url=cat.get("url"))
            self.stats.categories = len(
                [c for c in cat_repo.list_all() if c.parent_id is None]
            )
            self.stats.subcategories = len(
                [c for c in cat_repo.list_all() if c.parent_id is not None]
            )

        if not template_urls:
            print(
                "WARNING: No template pages discovered. "
                "Site may be protected by Cloudflare challenge or similar. "
                "Crawler will not attempt to bypass protections."
            )
            # Still log the attempt
            with get_db_session() as db:
                CrawlLogRepository(db).log(
                    self.settings.base_url + "/",
                    status_code=403,
                    status="blocked_or_challenge",
                    error_message="Discovery yielded zero template URLs – likely protection",
                )
            self.stats.print_summary()
            return self.stats

        # Limit if requested
        if max_pages is not None:
            template_urls = template_urls[:max_pages]

        print(f"Step 2–3: Crawling {len(template_urls)} template pages…")
        for i, url in enumerate(template_urls, 1):
            await self._process_page(url, discovery)
            if i % 10 == 0:
                print(f"  … processed {i}/{len(template_urls)}")

        # Final counts from DB
        with get_db_session() as db:
            stats_repo = StatsRepository(db)
            s = stats_repo.get_stats()
            self.stats.templates = s["total_templates"]
            self.stats.formats = s["total_formats"]
            self.stats.categories = s["total_categories"]
            self.stats.subcategories = s["total_subcategories"]

        self.stats.print_summary()
        return self.stats

    async def _process_page(self, url: str, discovery: Discovery) -> None:
        url = normalize_url(url, self.settings.base_url)

        with get_db_session() as db:
            tpl_repo = TemplateRepository(db)
            log_repo = CrawlLogRepository(db)

            if tpl_repo.should_skip(
                url,
                self.settings.crawl_interval_hours,
                force=self.settings.force_recrawl,
            ):
                self.stats.skipped += 1
                return

            html, status, err = await discovery.fetch(url)
            if not html:
                log_repo.log(url, status_code=status or None, status="error", error_message=err)
                self.stats.failed += 1
                return

            try:
                data = parse_template_page(html, url, self.settings.base_url)
            except Exception as e:
                log_repo.log(url, status_code=status, status="parse_error", error_message=str(e))
                self.stats.failed += 1
                return

            # Resolve category
            category_id = None
            cat_repo = CategoryRepository(db)
            if data.get("category_name"):
                parent = cat_repo.get_or_create(data["category_name"])
                category_id = parent.id
                if data.get("subcategory_name"):
                    sub = cat_repo.get_or_create(
                        data["subcategory_name"], parent_id=parent.id
                    )
                    category_id = sub.id

            page, created = tpl_repo.upsert_from_parsed(data, category_id=category_id)
            log_repo.log(url, status_code=status, status="ok")

            if created:
                self.stats.new_pages += 1
            else:
                self.stats.updated_pages += 1
            self.stats.successfully_crawled += 1


async def main(max_pages: Optional[int] = None):
    async with TemplateLabCrawler() as crawler:
        await crawler.run(max_pages=max_pages)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TemplateLab ethical crawler")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages for testing")
    args = parser.parse_args()
    asyncio.run(main(max_pages=args.max_pages))
