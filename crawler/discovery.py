"""Site structure discovery – categories, pagination, template URLs.

Respects robots.txt rules that are already known:
  Disallow: /download/, /files/, /wp-admin/, etc.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config import get_settings
from crawler.normalizer import is_template_page_url, normalize_url
from crawler.parser import parse_category_links, parse_listing_page
from crawler.rate_limiter import RateLimiter


class Discovery:
    def __init__(self, client: httpx.AsyncClient, rate_limiter: RateLimiter):
        self.client = client
        self.limiter = rate_limiter
        self.settings = get_settings()
        self.base = self.settings.base_url.rstrip("/")
        self.robots: Optional[RobotFileParser] = None
        self.discovered_categories: List[Dict] = []
        self.discovered_template_urls: Set[str] = set()
        self.visited_listings: Set[str] = set()

    async def load_robots(self) -> None:
        """Fetch and parse robots.txt. Fail open only for public content rules we already know."""
        rp = RobotFileParser()
        robots_url = f"{self.base}/robots.txt"
        try:
            async with self.limiter:
                resp = await self.client.get(robots_url, timeout=self.settings.request_timeout)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                # Known rules from earlier inspection
                rp.parse(
                    [
                        "User-agent: *",
                        "Disallow: /wp-admin/",
                        "Disallow: /wp-includes/",
                        "Disallow: /trackback/",
                        "Disallow: /wp-login.php",
                        "Disallow: /wp-register.php",
                        "Disallow: /download/",
                        "Disallow: /files/",
                        "Disallow: /cdn-cgi/",
                    ]
                )
        except Exception:
            rp.parse(
                [
                    "User-agent: *",
                    "Disallow: /download/",
                    "Disallow: /files/",
                    "Disallow: /wp-admin/",
                ]
            )
        self.robots = rp

    def allowed(self, url: str) -> bool:
        if not self.robots:
            return True
        return self.robots.can_fetch(self.settings.user_agent, url)

    async def fetch(self, url: str) -> tuple[Optional[str], int, Optional[str]]:
        """Return (html, status_code, error_message). Never bypass protections."""
        url = normalize_url(url, self.base)
        if not self.allowed(url):
            return None, 0, "robots.txt disallows"
        try:
            async with self.limiter:
                resp = await self.client.get(
                    url,
                    timeout=self.settings.request_timeout,
                    follow_redirects=True,
                )
            # Cloudflare challenge / block
            if resp.status_code in (403, 429, 503) or "cf-mitigated" in resp.headers.get(
                "cf-mitigated", ""
            ).lower() or "just a moment" in resp.text.lower()[:500]:
                return None, resp.status_code, "blocked_or_challenge"
            if resp.status_code >= 400:
                return None, resp.status_code, f"HTTP {resp.status_code}"
            return resp.text, resp.status_code, None
        except httpx.TimeoutException:
            return None, 0, "timeout"
        except Exception as e:
            return None, 0, str(e)[:300]

    async def discover_from_homepage(self) -> List[Dict]:
        html, status, err = await self.fetch(self.base + "/")
        if not html:
            return []
        cats = parse_category_links(html, self.base)
        # Also try common category archive patterns if menu is sparse
        self.discovered_categories = cats
        return cats

    async def crawl_listing(
        self, listing_url: str, max_pages: int = 30
    ) -> List[str]:
        """Follow pagination on a category/archive page and collect template URLs."""
        urls: List[str] = []
        current = listing_url
        pages = 0
        while current and pages < max_pages:
            if current in self.visited_listings:
                break
            self.visited_listings.add(current)
            html, status, err = await self.fetch(current)
            if not html:
                break
            result = parse_listing_page(html, self.base)
            for u in result["template_urls"]:
                if is_template_page_url(u) and self.allowed(u):
                    self.discovered_template_urls.add(u)
                    urls.append(u)
            next_p = result.get("next_page")
            if next_p and next_p != current and self.allowed(next_p):
                current = next_p
                pages += 1
            else:
                break
        return urls

    async def discover_all(self) -> Dict[str, List]:
        await self.load_robots()
        categories = await self.discover_from_homepage()
        all_templates: List[str] = []

        # Crawl each discovered category listing
        for cat in categories:
            cat_url = cat.get("url")
            if not cat_url or not self.allowed(cat_url):
                continue
            found = await self.crawl_listing(cat_url)
            all_templates.extend(found)

        # Also try a few well-known paths if homepage discovery yielded little
        fallback_paths = [
            "/category/business/",
            "/category/legal/",
            "/category/personal/",
            "/category/education/",
            "/templates/",
        ]
        for path in fallback_paths:
            url = self.base + path
            if url not in self.visited_listings and self.allowed(url):
                found = await self.crawl_listing(url)
                all_templates.extend(found)

        return {
            "categories": categories,
            "template_urls": list(self.discovered_template_urls),
        }
