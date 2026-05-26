from __future__ import annotations
import argparse
import gzip
import json
import sys
import time
import urllib.request
import urllib.error
import zlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from src.collectors.base import Article, USER_AGENT
from src.collectors.html_collector import is_allowed_by_robots
from src.deduplicator import _restore_article
from src.llm.gemini_client import GeminiClient


MIN_USABLE_BODY = 300
MIN_FALLBACK_BODY = 80
MAX_BODY_TO_GEMINI = 6000
FETCH_TIMEOUT = 15
FETCH_SLEEP = 1.0


def _is_google_news_url(url: str) -> bool:
    return "news.google.com" in url


CATEGORIES = ["新商品", "市場動向", "技術", "RTD", "規制", "原料", "海外", "国内", "その他"]


SYSTEM_PROMPT = """あなたはウイスキー業界紙（製造者・卸・営業向けプロ向け媒体）の編集者です。提供された記事情報を読み、業界紙向けの短い要約を作成してください。

【絶対ルール】
1. 提供されたテキスト（タイトル・本文）に明示的に書かれていない情報は絶対に含めない（推測・補完・想像・自分の知識による補強は全て禁止）
2. 数字・固有名詞・日付は提供されたテキストから正確に抜き出す
3. 不確かな情報・出典が曖昧な情報は key_facts に含めない
4. ウイスキー業界と直接関係ない記事 → relevance_score 1〜2、summary_ja 空、skip_reason 記入

【業界紙としての評価軸（relevance_score の重要な参考）】
- 業界プロが価値を感じる順：①市場・経済データ（出荷・売上・輸出統計・業績・M&A・株価）② 製造技術（蒸留・熟成・樽・酵母・原料）③ 規制・行政 ④ 重要な新商品・受賞 ⑤ 蒸留所動向（新設・拡張・閉鎖）⑥ 一般向けレビュー・タイアップ
- 具体的な数字（XX%増・XX億円・XX万ケース・XX年熟成 等）を含む記事は +1 加点
- 一般消費者向けレビュー、エンタメコラボ、芸能人イベント等は業界紙としての価値が低い → 5以下

【⭐ 新規性チェック（最重要）】
Google ニュースは「公開日が新しいが内容は古いニュースの再掲・常設紹介記事」を返すことがあります。以下のパターンは relevance_score 1〜3、skip_reason に「常設記事/過去ニュース再掲」と記入：
- 特定の日付イベントを伴わないブランド・会社の総合紹介
- 「○○の魅力」「おすすめ」「ランキング」「総まとめ」「比較」「完全ガイド」系
- 過去発売した商品の単なる紹介（"新発売"等の動詞がない、ブランド総体の紹介になっている）
- 一般論・解説記事・"知っておきたい"系
- タイトルから「いつ・何が起きたか」が読み取れない記事

逆に「業界紙が報じる価値あり」と判断するべきは：
- 「launched」「released」「announced」「reports」「earnings」「Q4 results」「completes」「acquires」
- 「発売」「リリース」「発表」「公開」「決算」「業績」「買収」「合意」
- 具体的日付＋具体的アクション・数字を伴う記事

【出力スキーマ（JSON）】
{
  "category": "新商品 | 市場動向 | 技術 | RTD | 規制 | 原料 | 海外 | 国内 | その他",
  "headline_ja": "30字以内の日本語見出し（記事内容を端的に。原文が英語でも日本語で書く）",
  "summary_ja": "80〜150字の日本語要約。提供テキストの事実のみ。一文で完結。数字や固有名詞があれば優先的に含める。",
  "key_facts": ["数字・固有名詞・日付など、提供テキストに明記されたファクトを最大3個（配列。各要素30字以内）"],
  "is_japanese_whisky_related": true/false,
  "relevance_score": 1から10の整数,
  "skip_reason": "掲載すべきでない場合の理由。掲載OKなら空文字"
}

【判定基準】
- category：
  新商品（リリース・限定品・再販）
  市場動向（出荷・消費・価格・M&A・業績・売上・輸出入統計）
  技術（蒸留・熟成・樽・酵母・発酵・原料処理技術）
  RTD（缶ハイボール・既製品ハイボール等）
  規制（酒税・行政・表示規制・輸出規制）
  原料（大麦・モルト・ピート・水）
  海外（日本以外で起きた話・スコッチ動向・台湾やインドなど）
  国内（日本国内の話）
  その他
- is_japanese_whisky_related：以下のいずれかに該当すれば true
  - 日本のメーカー（サントリー/ニッカ/イチローズ/月光川/サクラオ/ベンチャーウイスキー/堅展実業 等）の話
  - 日本国内の蒸留所動向
  - 日本市場における販売・輸入動向
  - 日本のコラボウイスキー（ファミマ等小売とのコラボも含む）
  - ジャパニーズウイスキーの海外露出・評価
  ※ 日本関連が少ない週はそれで構わない。無理に True にしない
- relevance_score：
  9-10: 業界全体に影響する重大ニュース（規制変更・大型M&A・主要メーカー業績発表・市場統計）
  7-8: 具体的数字を伴う市場動向・重要な技術ニュース・大手蒸留所の動向・象徴的新商品リリース
  5-6: 通常の新商品リリース・蒸留所開設・コラボ・受賞情報
  3-4: 一般向けレビュー・タイアップ企画・タレントイベント
  1-2: ウイスキー業界として価値が薄い／広告・無関係／本文取得失敗

【タイトルのみ入力の場合】
本文がなくタイトルしか提供されなくても、タイトルに記載された事実だけを使って要約・スコアリングしてください（スコア上限なし、ただし情報量が薄ければ自然と低スコアになる）。
"""


def _http_get(url: str) -> tuple[Optional[str], str]:
    """urllib で URL を取得。bytes/エンコーディング処理込み。失敗時は (None, original_url)。"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ja,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = resp.read()
            final_url = resp.url
            encoding = resp.headers.get("Content-Encoding", "")
            if encoding == "gzip":
                data = gzip.decompress(data)
            elif encoding == "deflate":
                data = zlib.decompress(data)
            charset = resp.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace"), final_url
    except Exception:
        return None, url


def fetch_article_body_with_canonical(url: str) -> tuple[Optional[str], str]:
    if _is_google_news_url(url):
        return None, url
    if not is_allowed_by_robots(url):
        return None, url

    html, canonical_url = _http_get(url)
    if html is None:
        return None, url

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "aside", "header", "footer", "form", "iframe", "noscript"]):
        tag.decompose()

    selectors = [
        "[itemprop=articleBody]",
        "article",
        "main",
        ".article-body",
        ".entry-content",
        ".post-content",
        ".article-content",
        "#content",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) >= MIN_USABLE_BODY:
                return text[:MAX_BODY_TO_GEMINI], canonical_url

    paragraphs = soup.find_all("p")
    if paragraphs:
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        if len(text) >= MIN_USABLE_BODY:
            return text[:MAX_BODY_TO_GEMINI], canonical_url

    return None, canonical_url


def build_user_content(article: Article, body_text: str) -> str:
    return (
        f"【記事情報】\n"
        f"- タイトル: {article.title}\n"
        f"- 媒体: {article.source_name}\n"
        f"- 公開日: {article.published_at.date().isoformat()}\n"
        f"- 原文言語: {'日本語' if article.language == 'ja' else '英語'}\n"
        f"- 本文:\n"
        f"{body_text}\n"
    )


def summarize_article(article: Article, client: GeminiClient) -> dict:
    fetched_body, canonical_url = fetch_article_body_with_canonical(article.url)

    if fetched_body and len(fetched_body) >= MIN_USABLE_BODY:
        body_text = fetched_body
        body_source = "fetched"
    elif len(article.body_text) >= MIN_USABLE_BODY:
        body_text = article.body_text[:MAX_BODY_TO_GEMINI]
        body_source = "rss"
    elif len(article.body_text) >= MIN_FALLBACK_BODY:
        body_text = article.body_text
        body_source = "rss_short"
    else:
        body_text = ""
        body_source = "title_only"

    user_content = build_user_content(article, body_text or "(本文取得失敗。タイトルのみから判断してください。)")
    try:
        result = client.generate_json(SYSTEM_PROMPT, user_content)
    except Exception as e:
        return {
            "category": "その他",
            "headline_ja": article.title[:30],
            "summary_ja": "",
            "key_facts": [],
            "is_japanese_whisky_related": False,
            "relevance_score": 1,
            "skip_reason": f"Gemini呼び出し失敗: {type(e).__name__}",
            "source_name": article.source_name,
            "source_url": canonical_url,
            "published_at": article.published_at.date().isoformat(),
            "language_original": article.language,
            "original_title": article.title,
            "body_source": body_source,
        }

    result["source_name"] = article.source_name
    result["source_url"] = canonical_url
    result["published_at"] = article.published_at.date().isoformat()
    result["language_original"] = article.language
    result["original_title"] = article.title
    result["body_source"] = body_source
    if "skip_reason" not in result:
        result["skip_reason"] = ""
    return result


def main():
    parser = argparse.ArgumentParser(description="要約モジュール（テストランナー）")
    parser.add_argument("--in", dest="input", required=True, help="重複排除済みJSON")
    parser.add_argument("--out", required=True, help="要約結果JSON")
    parser.add_argument("--limit", type=int, default=3, help="先頭から処理する件数（デフォルト3）")
    parser.add_argument("--offset", type=int, default=0, help="先頭からスキップする件数")
    parser.add_argument("--skip-seen", default=None, help="既存サマリJSON。そこに含まれる URL は処理しない")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_dotenv()

    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    pool = data["articles"][args.offset:]

    seen_urls: set[str] = set()
    if args.skip_seen and Path(args.skip_seen).exists():
        seen = json.loads(Path(args.skip_seen).read_text(encoding="utf-8-sig"))
        for a in seen.get("articles", []):
            seen_urls.add(a.get("source_url", ""))

    articles_data = []
    for a in pool:
        if a.get("url") in seen_urls:
            continue
        articles_data.append(a)
        if len(articles_data) >= args.limit:
            break
    articles = [_restore_article(a) for a in articles_data]

    print(f"[Summarizer] processing {len(articles)} articles…", file=sys.stderr)
    client = GeminiClient(verbose=args.verbose)

    def _flush(summaries_now: list) -> None:
        output = {
            "summarized_at": datetime.now().isoformat(),
            "input_source": args.input,
            "usage": client.usage_summary(),
            "article_count": len(summaries_now),
            "articles": summaries_now,
        }
        Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    summaries = []
    try:
        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {article.source_name}: {article.title[:60]}…", file=sys.stderr)
            s = summarize_article(article, client)
            if s:
                summaries.append(s)
            if i % 5 == 0:
                _flush(summaries)
                print(f"  [checkpoint] saved {len(summaries)} summaries", file=sys.stderr)
            time.sleep(FETCH_SLEEP)
    finally:
        _flush(summaries)

    print(f"\n[Summarizer] Done.", file=sys.stderr)
    print(f"  Gemini calls: {client.total_calls}", file=sys.stderr)
    print(f"  Tokens: in={client.total_input_tokens}, out={client.total_output_tokens}", file=sys.stderr)
    print(f"  Saved {len(summaries)} summaries to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
