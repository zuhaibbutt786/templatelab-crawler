"""Unit tests for URL and format normalizers."""

from crawler.normalizer import (
    extract_count_from_title,
    normalize_format,
    normalize_url,
)


def test_normalize_url_strips_tracking():
    url = "https://templatelab.com/foo/?utm_source=x&id=1"
    assert normalize_url(url) == "https://templatelab.com/foo?id=1"


def test_normalize_url_trailing_slash():
    assert normalize_url("https://templatelab.com/bar/") == "https://templatelab.com/bar"


def test_extract_count():
    assert extract_count_from_title("25 Business Proposal Templates") == 25
    assert extract_count_from_title("Free Invoice Templates") is None
    assert extract_count_from_title("10 Free Printable Templates") == 10


def test_normalize_format():
    assert normalize_format("DOCX") == "Word"
    assert normalize_format("xlsx") == "Excel"
    assert normalize_format("PPTX") == "PowerPoint"
    assert normalize_format("Google Docs") == "Google Docs"
    assert normalize_format("pdf") == "PDF"
