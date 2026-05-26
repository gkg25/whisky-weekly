from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse


USER_AGENT = "WhiskyWeekly/1.0 (+https://github.com/gkg25/whisky-weekly)"


@dataclass
class Article:
    source_name: str
    source_url: str
    title: str
    url: str
    published_at: datetime
    body_text: str = ""
    language: str = "en"
    collected_via: str = "rss"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return d


def parse_date_arg(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def end_of_day_utc(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path.rstrip("/") if p.path != "/" else "/"
    return urlunparse((p.scheme.lower(), netloc, path, "", "", ""))


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", flags=re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", flags=re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = _SCRIPT_RE.sub(" ", text)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()
