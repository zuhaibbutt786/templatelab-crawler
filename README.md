# TemplateLab Ethical Metadata Crawler

Python system that discovers publicly accessible TemplateLab category and template/article pages, extracts **metadata only** (no full article text, no template files), stores results in PostgreSQL, and exposes a read-only FastAPI search API.

## Ethical constraints

- Only publicly accessible information is collected.
- **Does not** bypass Cloudflare challenges, CAPTCHAs, authentication, paywalls, or robots.txt rules.
- Respects `robots.txt` (notably `Disallow: /download/`, `/files/`, `/wp-admin/`, …).
- Conservative rate limiting (`CRAWL_DELAY=2`, low concurrency).
- Stores titles, short descriptions/summaries, categories, formats, headings, public image URLs, related links — **never** full copyrighted article bodies or downloadable template documents.
- Logs HTTP errors (403, 404, 429, timeouts, challenges) and continues.

> **Note (2026):** TemplateLab is protected by Cloudflare. Simple HTTP clients often receive 403 / challenge pages. The crawler detects this, logs it, and does **not** attempt circumvention. Successful extraction requires the site to allow the crawler’s requests.

## Project structure

```
templatelab_crawler/
├── app/
│   ├── main.py          # FastAPI entry
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── api.py
├── crawler/
│   ├── crawler.py       # Orchestration
│   ├── discovery.py
│   ├── parser.py
│   ├── normalizer.py
│   └── rate_limiter.py
├── database/
│   └── repositories.py
├── exports/
│   ├── csv_export.py
│   ├── json_export.py
│   └── excel_export.py
├── tests/
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d db
# wait for healthy
docker compose run --rm crawler   # optional: limited crawl
docker compose up -d api
```

API: http://localhost:8000/docs

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Start Postgres (or use docker compose up -d db)
# Edit DATABASE_URL in .env if needed

# Initialize schema
python -c "from app.database import init_db; init_db()"

# Run crawler (respects robots + rate limits)
python -m crawler.crawler --max-pages 20

# Start API
uvicorn app.main:app --reload --port 8000
```

## Configuration (env)

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASE_URL` | postgresql://… | SQLAlchemy connection string |
| `CRAWL_DELAY` | 2.0 | Seconds between requests |
| `MAX_CONCURRENT_REQUESTS` | 2 | Parallel request limit |
| `REQUEST_TIMEOUT` | 30 | HTTP timeout (s) |
| `MAX_RETRIES` | 3 | (reserved) |
| `CRAWL_INTERVAL_HOURS` | 168 | Skip pages seen more recently |
| `FORCE_RECRAWL` | false | Ignore interval |
| `USER_AGENT` | TemplateLabEthicalCrawler/1.0 … | Identify the bot |

## API endpoints

- `GET /templates` — list / filter (`category`, `format`, `download_available`, `search`, `page`, `limit`)
- `GET /templates/{id}`
- `GET /categories`
- `GET /categories/{id}/templates`
- `GET /formats`
- `GET /search?q=invoice`
- `GET /stats`
- `GET /crawl/status`

Example:

```
GET /templates?category=Business&format=Word
GET /search?q=proposal
```

## Exports

```bash
python -m exports.csv_export
python -m exports.json_export
python -m exports.excel_export
```

Files land in `exports/data/`.

## Database schema

See `app/models.py`. Key tables:

- `categories` (hierarchical via `parent_id`)
- `template_pages` (unique `url`, metadata, `content_hash`, `last_seen_at`)
- `template_formats` + `page_formats`
- `page_sections`, `page_images`, `related_pages`
- `crawl_log`

Indexes include B-tree on common filters and a GIN full-text index on `title || description`.

## Incremental crawling

Before fetching a URL the crawler checks `last_seen_at`. Pages crawled within `CRAWL_INTERVAL_HOURS` are skipped unless `FORCE_RECRAWL=true`. Failed pages are logged; the crawl continues.

## Crawl summary output

At the end of each run:

```
Total URLs discovered:
New pages:
Updated pages:
Successfully crawled:
Failed:
Skipped:
Categories:
Subcategories:
Templates:
Formats:
Crawl duration:
```

## Tests

```bash
pytest tests/ -q
```

## License / usage

This software is provided for legitimate metadata research and indexing of publicly displayed information only. Users are responsible for complying with TemplateLab’s Terms of Service, robots.txt, copyright law, and applicable regulations. Do not use this code to scrape downloadable templates or full article text.
