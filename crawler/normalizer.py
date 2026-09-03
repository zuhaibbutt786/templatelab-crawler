"""URL and format normalization utilities."""

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import Optional, Set


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def normalize_url(url: str, base: str = "https://templatelab.com") -> str:
    """Normalize URL: absolute, strip fragment, remove tracking params, trailing slash consistency."""
    if not url:
        return ""
    # Make absolute
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = base.rstrip("/") + url
    elif not url.startswith("http"):
        url = base.rstrip("/") + "/" + url.lstrip("/")

    parsed = urlparse(url)
    # Keep only scheme, netloc, path, query (cleaned)
    query = parse_qs(parsed.query, keep_blank_values=False)
    cleaned = {k: v for k, v in query.items() if k.lower() not in TRACKING_PARAMS}
    new_query = urlencode(cleaned, doseq=True) if cleaned else ""

    # Prefer no trailing slash except for root
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse(
        (parsed.scheme or "https", parsed.netloc.lower(), path, "", new_query, "")
    )
    return normalized


def extract_count_from_title(title: str) -> Optional[int]:
    """Parse advertised template count from titles like '25 Business Proposal Templates'."""
    if not title:
        return None
    # Common patterns: leading number, or "X Free ..."
    patterns = [
        r"^(\d+)\s+",  # "25 Business..."
        r"(\d+)\s+(?:free\s+)?(?:printable\s+)?(?:downloadable\s+)?templates?",
        r"(\d+)\s+examples?",
        r"(\d+)\s+samples?",
    ]
    for pat in patterns:
        m = re.search(pat, title, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


# Format normalization map
FORMAT_MAP = {
    "doc": "Word",
    "docx": "Word",
    "word": "Word",
    "ms word": "Word",
    "microsoft word": "Word",
    "xls": "Excel",
    "xlsx": "Excel",
    "excel": "Excel",
    "ms excel": "Excel",
    "microsoft excel": "Excel",
    "pdf": "PDF",
    "ppt": "PowerPoint",
    "pptx": "PowerPoint",
    "powerpoint": "PowerPoint",
    "ms powerpoint": "PowerPoint",
    "microsoft powerpoint": "PowerPoint",
    "google docs": "Google Docs",
    "google doc": "Google Docs",
    "gdocs": "Google Docs",
    "google sheets": "Google Sheets",
    "google sheet": "Google Sheets",
    "gsheets": "Google Sheets",
    "odt": "Other",
    "ods": "Other",
    "rtf": "Other",
    "txt": "Other",
}


def normalize_format(raw: str) -> str:
    """Normalize a raw format string to a canonical name."""
    if not raw:
        return "Other"
    key = raw.strip().lower()
    # Remove file extension dots
    key = key.lstrip(".")
    return FORMAT_MAP.get(key, raw.strip().title() if len(raw) < 30 else "Other")


def is_template_page_url(url: str) -> bool:
    """Heuristic: most article/template pages are /slug/ under the domain."""
    if not url:
        return False
    parsed = urlparse(url)
    if "templatelab.com" not in parsed.netloc:
        return False
    path = parsed.path.strip("/")
    if not path:
        return False
    # Skip obvious non-content paths
    blocked_prefixes = (
        "wp-",
        "tag/",
        "category/",
        "author/",
        "page/",
        "feed",
        "sitemap",
        "robots",
        "download/",
        "files/",
        "cdn-cgi",
        "wp-json",
        "xmlrpc",
    )
    for b in blocked_prefixes:
        if path.startswith(b) or f"/{b}" in f"/{path}":
            return False
    # Typical single-segment or multi-segment slug pages
    return True


def content_hash(text: str) -> str:
    """SHA-256 of normalized text for change detection."""
    import hashlib

    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
