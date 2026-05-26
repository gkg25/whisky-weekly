from __future__ import annotations
import argparse
import json
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

from src.collectors.base import USER_AGENT


REQUEST_TIMEOUT = 15
MIN_BODY_LENGTH = 200
MAX_BODY_LENGTH = 10000
_BODY_SELECTORS = [
    "[itemprop=articleBody]",
    "article",
    "main",
    ".article-body",
    ".entry-content",
    ".post-content",
    ".article-content",
    "#content",
]

_robot_cache: dict[str, RobotFileParser] = {}


def is_allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in _robot_cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            return True
        _robot_cache[base] = rp
    return _robot_cache[base].can_fetch(USER_AGENT, url)


def fetch_article_body(url: str) -> Optional[str]:
    if not is_allowed_by_robots(url):
        return None
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.9"},
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup(["script", "style", "nav", "aside", "header", "footer", "form", "iframe", "noscript"]):
        tag.decompose()

    for selector in _BODY_SELECTORS:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) >= MIN_BODY_LENGTH:
                return text[:MAX_BODY_LENGTH]

    paragraphs = soup.find_all("p")
    if paragraphs:
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        if len(text) >= MIN_BODY_LENGTH:
            return text[:MAX_BODY_LENGTH]

    return None


def main():
    parser = argparse.ArgumentParser(description="HTML body fetcher (test runner)")
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    body = fetch_article_body(args.url)
    if body is None:
        print(json.dumps({"url": args.url, "ok": False, "reason": "fetch failed or robots disallowed"}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"url": args.url, "ok": True, "length": len(body), "preview": body[:500]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
