from __future__ import annotations
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from src.collectors.base import Article, normalize_url


_TITLE_TOKEN_RE = re.compile(r"[A-Za-z0-9぀-ゟ゠-ヿ一-鿿]+")
_TITLE_SOURCE_SEP_RE = re.compile(r"\s+[-–|｜]\s+")


def _title_signature(title: str) -> set[str]:
    title = title.lower().strip()
    title = _TITLE_SOURCE_SEP_RE.split(title)[0]
    tokens = _TITLE_TOKEN_RE.findall(title)
    return {t for t in tokens if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _is_google_news_url(url: str) -> bool:
    return "news.google.com" in url


def _better_article(a: Article, b: Article) -> Article:
    a_gn = _is_google_news_url(a.url)
    b_gn = _is_google_news_url(b.url)
    if a_gn and not b_gn:
        return b
    if b_gn and not a_gn:
        return a
    if len(a.body_text) >= len(b.body_text):
        return a
    return b


def load_seen_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {normalize_url(u) for u in data.get("urls", [])}


def save_seen_urls(path: Path, urls: Iterable[str]) -> None:
    data = {"urls": sorted({normalize_url(u) for u in urls})}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def dedupe(
    articles: list[Article],
    seen_urls: Optional[set[str]] = None,
    title_threshold: float = 0.65,
) -> tuple[list[Article], dict]:
    seen_urls = seen_urls or set()
    diag = {
        "input_count": len(articles),
        "removed_seen": 0,
        "removed_url_duplicate": 0,
        "removed_title_duplicate": 0,
    }

    after_seen = []
    for a in articles:
        if normalize_url(a.url) in seen_urls:
            diag["removed_seen"] += 1
        else:
            after_seen.append(a)

    by_norm_url: dict[str, Article] = {}
    for a in after_seen:
        nu = normalize_url(a.url)
        if nu in by_norm_url:
            diag["removed_url_duplicate"] += 1
            by_norm_url[nu] = _better_article(by_norm_url[nu], a)
        else:
            by_norm_url[nu] = a
    after_url = list(by_norm_url.values())

    by_lang: dict[str, list[Article]] = {}
    for a in after_url:
        by_lang.setdefault(a.language, []).append(a)

    result: list[Article] = []
    for lang_articles in by_lang.values():
        lang_articles.sort(key=lambda x: x.published_at)
        signatures = [_title_signature(a.title) for a in lang_articles]
        kept: list[int] = []
        for i, a in enumerate(lang_articles):
            dup_of: Optional[int] = None
            for ki in kept:
                if _jaccard(signatures[i], signatures[ki]) >= title_threshold:
                    dup_of = ki
                    break
            if dup_of is None:
                kept.append(i)
            else:
                diag["removed_title_duplicate"] += 1
                better = _better_article(lang_articles[dup_of], a)
                if better is a:
                    lang_articles[dup_of] = a
                    signatures[dup_of] = signatures[i]
        for ki in kept:
            result.append(lang_articles[ki])

    diag["output_count"] = len(result)
    result.sort(key=lambda a: a.published_at, reverse=True)
    return result, diag


def _restore_article(d: dict) -> Article:
    return Article(
        source_name=d["source_name"],
        source_url=d["source_url"],
        title=d["title"],
        url=d["url"],
        published_at=datetime.fromisoformat(d["published_at"]),
        body_text=d.get("body_text", ""),
        language=d.get("language", "en"),
        collected_via=d.get("collected_via", "rss"),
    )


def main():
    parser = argparse.ArgumentParser(description="重複排除（テストランナー）")
    parser.add_argument("--in", dest="input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seen-urls", default="data/seen_urls.json")
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--update-seen", action="store_true", help="出力URL を seen_urls.json に追記")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    articles = [_restore_article(a) for a in data["articles"]]

    seen_urls = load_seen_urls(Path(args.seen_urls))
    deduped, diag = dedupe(articles, seen_urls, title_threshold=args.threshold)

    output = {
        "deduped_at": datetime.now().isoformat(),
        "input_source": args.input,
        "threshold": args.threshold,
        "diagnostics": diag,
        "article_count": len(deduped),
        "articles": [a.to_dict() for a in deduped],
    }
    Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dedup: {diag['input_count']} -> {diag['output_count']}")
    print(f"  removed_seen:           {diag['removed_seen']}")
    print(f"  removed_url_duplicate:  {diag['removed_url_duplicate']}")
    print(f"  removed_title_duplicate:{diag['removed_title_duplicate']}")
    print(f"Saved to {args.out}")

    if args.update_seen:
        new_seen = seen_urls | {normalize_url(a.url) for a in deduped}
        save_seen_urls(Path(args.seen_urls), new_seen)
        print(f"Updated {args.seen_urls} ({len(new_seen)} URLs)")


if __name__ == "__main__":
    main()
