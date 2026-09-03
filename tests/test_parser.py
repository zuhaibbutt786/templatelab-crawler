"""Parser unit tests with synthetic HTML."""

from crawler.parser import parse_template_page, parse_listing_page


SAMPLE_PAGE = """
<html>
<head>
  <title>25 Business Proposal Templates</title>
  <meta name="description" content="A short public description of proposal templates.">
</head>
<body>
  <article>
    <h1 class="entry-title">25 Business Proposal Templates</h1>
    <time datetime="2023-05-10">May 10, 2023</time>
    <div class="entry-content">
      <p>This collection offers professional proposal templates for small businesses.</p>
      <h2>Word Templates</h2>
      <a href="/download/sample.docx">Download DOCX</a>
      <a href="#">PDF Version</a>
      <img src="/wp-content/uploads/preview1.jpg" alt="Proposal preview">
    </div>
  </article>
  <div class="related-posts">
    <a href="https://templatelab.com/invoice-templates/">Invoice Templates</a>
  </div>
</body>
</html>
"""


def test_parse_template_page():
    data = parse_template_page(SAMPLE_PAGE, "https://templatelab.com/business-proposal-templates/")
    assert data["title"] == "25 Business Proposal Templates"
    assert data["advertised_count"] == 25
    assert "Word" in data["formats"] or "PDF" in data["formats"]
    assert data["download_available"] is True
    assert data["publication_date"] is not None
    assert len(data["images"]) >= 1
    assert any("invoice" in u for u in data["related_urls"])


def test_parse_listing():
    html = """
    <html><body>
      <article><h2><a href="/foo-templates/">Foo Templates</a></h2></article>
      <a class="next" href="/category/business/page/2/">Next</a>
    </body></html>
    """
    result = parse_listing_page(html)
    assert any("foo-templates" in u for u in result["template_urls"])
    assert result["next_page"] is not None
