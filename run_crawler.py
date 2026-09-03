#!/usr/bin/env python3
"""Convenience entry point for the crawler."""

import asyncio
import argparse

from crawler.crawler import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TemplateLab ethical metadata crawler")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional limit on number of template pages to process (useful for testing)",
    )
    args = parser.parse_args()
    asyncio.run(main(max_pages=args.max_pages))
