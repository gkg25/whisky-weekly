from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from src.collectors import rss_collector, google_news_collector
from src.collectors.base import parse_date_arg, end_of_day_utc, normalize_url
from src.deduplicator import dedupe, load_seen_urls, save_seen_urls
from src.summarizer import summarize_article, FETCH_SLEEP
from src.llm.gemini_client import GeminiClient
from src.pdf_builder import select_articles, render_html, html_to_pdf, load_issue_number
from src.mailer import send_email


def main():
    parser = argparse.ArgumentParser(description="Whisky Weekly end-to-end pipeline")
    parser.add_argument("--from", dest="since", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="until", required=True, help="YYYY-MM-DD")
    parser.add_argument("--send", action="store_true", help="生成後にメール送信")
    parser.add_argument("--max", type=int, default=50, help="PDF掲載最大記事数")
    parser.add_argument("--min-score", type=int, default=4)
    parser.add_argument("--summarize-limit", type=int, default=80, help="Gemini要約する最大記事数")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--no-advance-counter", action="store_true")
    parser.add_argument("--no-update-seen", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_dotenv()

    since = parse_date_arg(args.since)
    until = end_of_day_utc(parse_date_arg(args.until))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir)
    seen_urls_path = data_dir / "seen_urls.json"
    counter_path = data_dir / "issue_counter.json"

    print(f"=== Whisky Weekly Pipeline ===", file=sys.stderr)
    print(f"Period: {args.since} ~ {args.until}", file=sys.stderr)
    print(f"", file=sys.stderr)

    print(f"[1/5] Collecting articles...", file=sys.stderr)
    rss_articles, _ = rss_collector.collect_all(since, until)
    print(f"  RSS: {len(rss_articles)}", file=sys.stderr)
    gn_articles, _ = google_news_collector.collect_all(since, until)
    print(f"  Google News: {len(gn_articles)}", file=sys.stderr)
    raw_articles = rss_articles + gn_articles
    print(f"  Total raw: {len(raw_articles)}", file=sys.stderr)

    print(f"\n[2/5] Deduplicating...", file=sys.stderr)
    seen_urls = load_seen_urls(seen_urls_path)
    print(f"  Pre-seen URLs: {len(seen_urls)}", file=sys.stderr)
    deduped, dedup_diag = dedupe(raw_articles, seen_urls)
    print(f"  {dedup_diag['input_count']} -> {dedup_diag['output_count']}", file=sys.stderr)

    print(f"\n[3/5] Summarizing (Gemini, limit {args.summarize_limit})...", file=sys.stderr)
    client = GeminiClient(verbose=args.verbose)
    candidates = deduped[: args.summarize_limit]
    summaries = []
    for i, article in enumerate(candidates, 1):
        if i % 5 == 0 or args.verbose:
            print(f"  [{i}/{len(candidates)}]", file=sys.stderr)
        s = summarize_article(article, client)
        if s:
            summaries.append(s)
        time.sleep(FETCH_SLEEP)
    print(f"  Summarized: {len(summaries)} / {len(candidates)}", file=sys.stderr)
    print(f"  Gemini calls: {client.total_calls}, tokens in/out: {client.total_input_tokens}/{client.total_output_tokens}", file=sys.stderr)

    summary_path = output_dir / f"summary_{args.since}_{args.until}.json"
    summary_path.write_text(json.dumps({
        "summarized_at": datetime.now().isoformat(),
        "usage": client.usage_summary(),
        "period": {"from": args.since, "to": args.until},
        "article_count": len(summaries),
        "articles": summaries,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[4/5] Generating PDF...", file=sys.stderr)
    issue_number = load_issue_number(counter_path, advance=not args.no_advance_counter)
    selected = select_articles(summaries, max_total=args.max, min_score=args.min_score)
    print(f"  Issue #{issue_number}, selected {len(selected)} / {len(summaries)}", file=sys.stderr)

    today_str = date.today().isoformat()
    html = render_html(
        selected=selected,
        issue_number=issue_number,
        issue_date=today_str,
        period_start=args.since,
        period_end=args.until,
    )
    pdf_path = output_dir / f"whisky_weekly_{args.since}_{args.until}.pdf"
    html_to_pdf(html, pdf_path)
    print(f"  Saved: {pdf_path}", file=sys.stderr)

    if not args.no_update_seen:
        new_seen = seen_urls | {normalize_url(a["source_url"]) for a in selected if a.get("source_url")}
        save_seen_urls(seen_urls_path, new_seen)
        print(f"  Updated seen_urls.json ({len(new_seen)} URLs)", file=sys.stderr)

    if args.send:
        print(f"\n[5/5] Sending email...", file=sys.stderr)
        sender = os.environ.get("GMAIL_ADDRESS")
        password = os.environ.get("GMAIL_APP_PASSWORD")
        recipient_value = os.environ.get("RECIPIENT_EMAIL")
        if not sender or not password or not recipient_value:
            print("  ERROR: GMAIL_ADDRESS / GMAIL_APP_PASSWORD / RECIPIENT_EMAIL 必須", file=sys.stderr)
            sys.exit(2)
        body_text = (
            f"Whisky Weekly 第{issue_number}号をお届けします。\n\n"
            f"対象期間: {args.since}〜{args.until}\n"
            f"掲載記事数: {len(selected)}\n\n"
            f"今週のヘッドライン:\n"
        )
        for a in selected[:5]:
            body_text += f"  ・{a.get('headline_ja', '')}\n"
        body_text += f"\n詳細は添付PDFをご覧ください。\n\n本ニュースは AI が公開情報をもとに自動生成しています。"
        recipient_list = send_email(
            sender=sender,
            password=password,
            recipients=recipient_value,
            subject=f"[Whisky Weekly 第{issue_number}号] {args.since}〜{args.until} 業界ニュース",
            body_text=body_text,
            attachments=[pdf_path],
        )
        print(f"  Sent to {len(recipient_list)} recipients (BCC): {recipient_list}", file=sys.stderr)
    else:
        print(f"\n[5/5] Skipped email (use --send to enable)", file=sys.stderr)

    print(f"\n=== Done ===", file=sys.stderr)


if __name__ == "__main__":
    main()
