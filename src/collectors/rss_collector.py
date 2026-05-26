from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Iterable, Optional
import feedparser
from dateutil import parser as dateparser

from src.collectors.base import Article, USER_AGENT, parse_date_arg, end_of_day_utc, strip_html
from src.config import SOURCES, Source


SLEEP_BETWEEN_FETCHES = 1.0


def _parse_published(entry) -> Optional[datetime]:
    for key in ("published", "updated", "created"):
        val = entry.get(key) if hasattr(entry, "get") else None
        if val:
            try:
                dt = dateparser.parse(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    return None


def _extract_body(entry) -> str:
    content = entry.get("content")
    if content and isinstance(content, list) and len(content) > 0:
        value = content[0].get("value") if isinstance(content[0], dict) else getattr(content[0], "value", None)
        if value:
            return strip_html(value)
    summary = entry.get("summary") or entry.get("description") or ""
    return strip_html(summary)


def collect_from_source(source: Source, since: datetime, until: datetime) -> list[Article]:
    if not source.rss_url:
        return []
    feed = feedparser.parse(source.rss_url, agent=USER_AGENT)
    articles: list[Article] = []
    for entry in feed.entries:
        pub = _parse_published(entry)
        if pub is None:
            continue
        if pub < since or pub > until:
            continue
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        articles.append(Article(
            source_name=source.name,
            source_url=source.homepage,
            title=title,
            url=url,
            published_at=pub,
            body_text=_extract_body(entry),
            language=source.language,
            collected_via="rss",
        ))
    return articles


def collect_all(since: datetime, until: datetime, sources: Optional[Iterable[Source]] = None) -> tuple[list[Article], dict]:
    if sources is None:
        sources = SOURCES
    all_articles: list[Article] = []
    diag = {"sources": []}
    for source in sources:
        if not source.rss_url:
            diag["sources"].append({"name": source.name, "rss_url": None, "count": 0, "status": "no_rss_configured"})
            continue
        try:
            articles = collect_from_source(source, since, until)
            all_articles.extend(articles)
            diag["sources"].append({
                "name": source.name,
                "rss_url": source.rss_url,
                "count": len(articles),
                "status": "ok",
            })
        except Exception as e:
            diag["sources"].append({
                "name": source.name,
                "rss_url": source.rss_url,
                "count": 0,
                "status": f"error: {type(e).__name__}: {e}",
            })
        time.sleep(SLEEP_BETWEEN_FETCHES)
    return all_articles, diag


def main():
    parser = argparse.ArgumentParser(description="RSS based collector (test runner)")
    parser.add_argument("--from", dest="since", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="until", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    since = parse_date_arg(args.since)
    until = end_of_day_utc(parse_date_arg(args.until))

    articles, diag = collect_all(since, until)
    output = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "diagnostics": diag,
        "article_count": len(articles),
        "articles": [a.to_dict() for a in articles],
    }
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved {len(articles)} articles to {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
