from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote
import feedparser
from dateutil import parser as dateparser

from src.collectors.base import Article, USER_AGENT, parse_date_arg, end_of_day_utc, strip_html
from src.config import GOOGLE_NEWS_QUERIES


SLEEP_BETWEEN_FETCHES = 1.0


def _build_url(q: dict) -> str:
    return (
        f"https://news.google.com/rss/search?q={quote(q['q'])}"
        f"&hl={q['hl']}&gl={q['gl']}&ceid={q['ceid']}"
    )


def _parse_published(entry) -> Optional[datetime]:
    for key in ("published", "updated"):
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


def _extract_source_name(entry) -> str:
    src = entry.get("source") if hasattr(entry, "get") else None
    if src:
        if isinstance(src, dict):
            return src.get("title") or "Google News"
        title = getattr(src, "title", None)
        if title:
            return title
    return "Google News"


def collect_from_query(query: dict, since: datetime, until: datetime) -> list[Article]:
    url = _build_url(query)
    feed = feedparser.parse(url, agent=USER_AGENT)
    articles: list[Article] = []
    for entry in feed.entries:
        pub = _parse_published(entry)
        if pub is None:
            continue
        if pub < since or pub > until:
            continue
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        articles.append(Article(
            source_name=_extract_source_name(entry),
            source_url=link,
            title=title,
            url=link,
            published_at=pub,
            body_text=strip_html(entry.get("summary", "") or ""),
            language=query["hl"],
            collected_via="google_news",
        ))
    return articles


def collect_all(since: datetime, until: datetime, queries: Optional[list[dict]] = None) -> tuple[list[Article], dict]:
    if queries is None:
        queries = GOOGLE_NEWS_QUERIES
    all_articles: list[Article] = []
    diag = {"queries": []}
    for q in queries:
        try:
            arts = collect_from_query(q, since, until)
            all_articles.extend(arts)
            diag["queries"].append({"q": q["q"], "lang": q["hl"], "count": len(arts), "status": "ok"})
        except Exception as e:
            diag["queries"].append({"q": q["q"], "lang": q["hl"], "count": 0, "status": f"error: {type(e).__name__}: {e}"})
        time.sleep(SLEEP_BETWEEN_FETCHES)
    return all_articles, diag


def main():
    parser = argparse.ArgumentParser(description="Google News RSS collector (test runner)")
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
