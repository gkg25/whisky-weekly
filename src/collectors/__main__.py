from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone

from src.collectors import rss_collector, google_news_collector
from src.collectors.base import parse_date_arg, end_of_day_utc


def main():
    parser = argparse.ArgumentParser(description="全コレクタを実行（RSS + Google News）")
    parser.add_argument("--from", dest="since", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="until", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", default=None)
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--skip-google", action="store_true")
    args = parser.parse_args()

    since = parse_date_arg(args.since)
    until = end_of_day_utc(parse_date_arg(args.until))

    all_articles = []
    full_diag = {}

    if not args.skip_rss:
        print("[1/2] RSS 収集中…", file=sys.stderr)
        rss_articles, rss_diag = rss_collector.collect_all(since, until)
        all_articles.extend(rss_articles)
        full_diag["rss"] = rss_diag
        print(f"  → {len(rss_articles)} 件", file=sys.stderr)

    if not args.skip_google:
        print("[2/2] Google ニュース RSS 収集中…", file=sys.stderr)
        gn_articles, gn_diag = google_news_collector.collect_all(since, until)
        all_articles.extend(gn_articles)
        full_diag["google_news"] = gn_diag
        print(f"  → {len(gn_articles)} 件", file=sys.stderr)

    output = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "diagnostics": full_diag,
        "article_count": len(all_articles),
        "articles": [a.to_dict() for a in all_articles],
    }
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved {len(all_articles)} articles to {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
