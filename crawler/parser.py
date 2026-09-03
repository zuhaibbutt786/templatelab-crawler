"""HTML parsing for TemplateLab pages – metadata only, no full article text."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from crawler.normalizer import (
    extract_count_from_title,
    normalize_format,
    normalize_url,
)


def _text(el: Optional[Tag]) -> str:
    if not el:
        return ""
    return " ".join(el.stripped_strings)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(raw[:30], fmt).date()
        except ValueError:
            continue
    # ISO-ish
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def parse_category_links(html: str, base_url: str = "https://templatelab.com") -> List[Dict[str, Any]]:
    """Extract main navigation / category links from homepage or menu."""
    soup = BeautifulSoup(html, "lxml")
    found: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    # Common WP nav selectors
    selectors = [
        "nav a",
        ".menu a",
        "#menu-main a",
        ".main-navigation a",
        "header a",
        ".categories a",
        "ul.menu li a",
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            name = _text(a)
            if not href or not name or len(name) < 2:
                continue
            url = normalize_url(urljoin(base_url, href), base_url)
            if url in seen or "templatelab.com" not in url:
                continue
            # Skip pure utility links
            if any(
                x in url.lower()
                for x in ("/tag/", "/author/", "/page/", "wp-", "login", "register", "cart", "account")
            ):
                continue
            seen.add(url)
            found.append({"name": name.strip(), "url": url})
    return found


def parse_listing_page(
    html: str, base_url: str = "https://templatelab.com"
) -> Dict[str, Any]:
    """Parse a category/archive listing: template page links + pagination."""
    soup = BeautifulSoup(html, "lxml")
    template_urls: List[str] = []
    next_page: Optional[str] = None
    seen: Set[str] = set()

    # Article / post links
    for a in soup.select("article a, .post a, .entry-title a, h2 a, h3 a, .card a"):
        href = a.get("href")
        if not href:
            continue
        url = normalize_url(urljoin(base_url, href), base_url)
        if url in seen or "templatelab.com" not in url:
            continue
        path = url.split("templatelab.com")[-1]
        if any(
            x in path
            for x in ("/category/", "/tag/", "/page/", "/author/", "wp-", "/feed")
        ):
            continue
        # Prefer deeper content pages
        if path.count("/") >= 1 and len(path) > 3:
            seen.add(url)
            template_urls.append(url)

    # Pagination
    for a in soup.select("a.next, .next a, a[rel='next'], .pagination a, .nav-links a"):
        text = _text(a).lower()
        href = a.get("href")
        if href and ("next" in text or "»" in text or ">" in text or a.get("rel") == "next"):
            next_page = normalize_url(urljoin(base_url, href), base_url)
            break

    # Fallback: look for /page/N/
    if not next_page:
        for a in soup.select("a[href*='/page/']"):
            href = a.get("href")
            if href:
                next_page = normalize_url(urljoin(base_url, href), base_url)
                break

    return {"template_urls": template_urls, "next_page": next_page}


def parse_template_page(
    html: str, url: str, base_url: str = "https://templatelab.com"
) -> Dict[str, Any]:
    """
    Extract structured metadata from a single template/article page.
    Does NOT store full article body.
    """
    soup = BeautifulSoup(html, "lxml")

    # Title
    title = ""
    for sel in ("h1.entry-title", "h1.post-title", "article h1", "h1", "title"):
        el = soup.select_one(sel)
        if el:
            title = _text(el)
            if title and title.lower() not in ("templatelab", "home"):
                break
    if not title:
        title = soup.title.string.strip() if soup.title and soup.title.string else url

    advertised_count = extract_count_from_title(title)

    # Short description / excerpt (meta or first paragraph summary)
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()[:500]
    if not description:
        # First meaningful paragraph only – still a short summary
        for p in soup.select("article p, .entry-content p, .post-content p"):
            t = _text(p)
            if len(t) > 40:
                description = t[:400] + ("…" if len(t) > 400 else "")
                break

    # Dates
    publication_date = None
    updated_date = None
    for time_el in soup.select("time, .published, .entry-date, .post-date"):
        dt = time_el.get("datetime") or _text(time_el)
        parsed = _parse_date(dt)
        if parsed and not publication_date:
            publication_date = parsed
    # Look for "Updated" text
    body_text = soup.get_text(" ", strip=True)[:3000]
    m = re.search(r"(?:updated|last\s+updated|modified)[:\s]+([A-Za-z0-9,\s/-]+)", body_text, re.I)
    if m:
        updated_date = _parse_date(m.group(1))

    # Formats – look for download buttons, file type labels, icons
    formats: Set[str] = set()
    format_keywords = [
        "docx", "doc", "word", "xlsx", "xls", "excel", "pdf",
        "pptx", "ppt", "powerpoint", "google docs", "google sheets",
    ]
    for el in soup.select("a, span, div, button, li"):
        txt = _text(el).lower()
        href = (el.get("href") or "").lower()
        combined = txt + " " + href
        for kw in format_keywords:
            if kw in combined:
                formats.add(normalize_format(kw))
    # Meta / structured
    for meta in soup.find_all("meta"):
        content = (meta.get("content") or "").lower()
        for kw in format_keywords:
            if kw in content:
                formats.add(normalize_format(kw))

    download_available = bool(formats) or bool(
        soup.select("a[href*='download'], .download, .btn-download, a.download")
    )

    # Category / breadcrumb
    category_name = None
    subcategory_name = None
    for a in soup.select(".breadcrumb a, .breadcrumbs a, nav.breadcrumb a, .cat-links a"):
        name = _text(a)
        href = a.get("href") or ""
        if name and "home" not in name.lower() and "templatelab" not in name.lower():
            if not category_name:
                category_name = name
            else:
                subcategory_name = name

    # Headings (structure only)
    headings: List[Dict[str, Any]] = []
    for i, h in enumerate(soup.select("article h2, .entry-content h2, .post-content h2, article h3")):
        t = _text(h)
        if t and len(t) < 200:
            headings.append({"heading": t, "position": i})

    # Images (publicly displayed template previews)
    images: List[Dict[str, Any]] = []
    for i, img in enumerate(soup.select("article img, .entry-content img, .post-content img, .template-preview img")):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        src = normalize_url(urljoin(base_url, src), base_url)
        alt = img.get("alt") or ""
        # Skip tiny icons / logos
        if any(x in src.lower() for x in ("logo", "icon", "avatar", "emoji", "spinner")):
            continue
        images.append({"image_url": src, "alt_text": alt[:300], "position": i})
        if len(images) >= 20:  # reasonable limit
            break

    # Related posts
    related_urls: List[str] = []
    for a in soup.select(
        ".related a, .related-posts a, .you-may-also-like a, .similar a, aside a"
    ):
        href = a.get("href")
        if href:
            u = normalize_url(urljoin(base_url, href), base_url)
            if "templatelab.com" in u and u != url:
                related_urls.append(u)

    template_type = None
    if "template" in title.lower():
        template_type = "Template Collection"
    elif "form" in title.lower():
        template_type = "Form"
    elif "letter" in title.lower():
        template_type = "Letter"
    elif "agreement" in title.lower() or "contract" in title.lower():
        template_type = "Legal"

    return {
        "url": normalize_url(url, base_url),
        "title": title[:500],
        "description": description,
        "advertised_count": advertised_count,
        "publication_date": publication_date,
        "updated_date": updated_date,
        "download_available": download_available,
        "formats": sorted(formats),
        "category_name": category_name,
        "subcategory_name": subcategory_name,
        "headings": headings,
        "images": images,
        "related_urls": list(dict.fromkeys(related_urls))[:15],
        "template_type": template_type,
    }
