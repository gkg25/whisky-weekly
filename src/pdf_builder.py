from __future__ import annotations
import argparse
import json
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright


TEMPLATES_DIR = Path(__file__).parent / "templates"


CATEGORY_ORDER = ["新商品", "市場動向", "技術", "RTD", "規制", "原料", "海外", "国内", "その他"]


def _sort_key(a: dict) -> tuple:
    score = int(a.get("relevance_score") or 0)
    japan_flag = bool(a.get("is_japanese_whisky_related"))
    return (-score, 0 if japan_flag else 1)


def select_articles(articles: list[dict], max_total: int = 50, min_score: int = 4) -> list[dict]:
    candidates = [
        a for a in articles
        if not a.get("skip_reason")
        and a.get("summary_ja")
        and (a.get("relevance_score") or 0) >= min_score
    ]
    candidates.sort(key=lambda a: a.get("published_at", ""), reverse=True)
    candidates.sort(key=_sort_key)
    return candidates[:max_total]


def group_by_category(articles: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for a in articles:
        cat = a.get("category") or "その他"
        if cat not in CATEGORY_ORDER:
            cat = "その他"
        groups[cat].append(a)
    ordered = {}
    for cat in CATEGORY_ORDER:
        if cat in groups and groups[cat]:
            ordered[cat] = groups[cat]
    return ordered


def collect_sources(articles: list[dict]) -> list[dict]:
    seen = set()
    sources = []
    for a in articles:
        key = (a.get("source_name"), a.get("source_url"))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "name": a.get("source_name", ""),
            "url": a.get("source_url", ""),
            "date": a.get("published_at", ""),
        })
    sources.sort(key=lambda s: s["name"])
    return sources


def load_issue_number(counter_path: Path, advance: bool) -> int:
    if counter_path.exists():
        data = json.loads(counter_path.read_text(encoding="utf-8"))
    else:
        data = {"current_issue": 0, "last_published_at": None}
    next_num = (data.get("current_issue") or 0) + 1
    if advance:
        data["current_issue"] = next_num
        data["last_published_at"] = datetime.now().isoformat()
        counter_path.parent.mkdir(parents=True, exist_ok=True)
        counter_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return next_num


def render_html(
    selected: list[dict],
    issue_number: int,
    issue_date: str,
    period_start: str,
    period_end: str,
    headline_count: int = 5,
) -> str:
    css = (TEMPLATES_DIR / "style.css").read_text(encoding="utf-8")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("newsletter.html")

    featured = selected[0] if selected else None
    headlines_pool = selected[:headline_count]
    rest = selected[1:] if featured else selected
    categories = group_by_category(rest)
    sources = collect_sources(selected)

    return template.render(
        css=css,
        issue_number=issue_number,
        issue_date=issue_date,
        period_start=period_start,
        period_end=period_end,
        headlines=headlines_pool,
        featured=featured,
        categories=categories,
        sources=sources,
        unverified=[],
    )


def html_to_pdf(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="ニュースレターPDF生成")
    parser.add_argument("--in", dest="input", required=True, help="要約済みJSON")
    parser.add_argument("--out", required=True, help="PDF出力先")
    parser.add_argument("--html-out", default=None, help="中間HTMLの出力先（デバッグ用）")
    parser.add_argument("--issue", type=int, default=None, help="号数を強制指定（テスト用）")
    parser.add_argument("--advance-counter", action="store_true", help="data/issue_counter.json を進める")
    parser.add_argument("--counter-file", default="data/issue_counter.json")
    parser.add_argument("--max", type=int, default=50, help="掲載最大記事数")
    parser.add_argument("--min-score", type=int, default=3, help="relevance_score 最低値")
    parser.add_argument("--period-start", default=None)
    parser.add_argument("--period-end", default=None)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    articles = data.get("articles", [])

    selected = select_articles(articles, max_total=args.max, min_score=args.min_score)
    print(f"[PDF] selected {len(selected)} of {len(articles)} articles")

    if args.issue is not None:
        issue_number = args.issue
    else:
        issue_number = load_issue_number(Path(args.counter_file), advance=args.advance_counter)

    today = date.today().isoformat()

    html = render_html(
        selected=selected,
        issue_number=issue_number,
        issue_date=today,
        period_start=args.period_start or "—",
        period_end=args.period_end or "—",
    )

    if args.html_out:
        Path(args.html_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.html_out).write_text(html, encoding="utf-8")
        print(f"[PDF] saved intermediate HTML to {args.html_out}")

    html_to_pdf(html, Path(args.out))
    print(f"[PDF] saved PDF to {args.out}")


if __name__ == "__main__":
    main()
