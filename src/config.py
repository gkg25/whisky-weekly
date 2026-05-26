from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Source:
    name: str
    homepage: str
    rss_url: Optional[str]
    language: str


SOURCES: list[Source] = [
    Source("The Drinks Business", "https://www.thedrinksbusiness.com/", "https://www.thedrinksbusiness.com/feed/", "en"),
    Source("The Spirits Business", "https://www.thespiritsbusiness.com/", "https://www.thespiritsbusiness.com/feed/", "en"),
    Source("Drinks Retailing News", "https://drinksretailingnews.co.uk/", "https://drinksretailingnews.co.uk/feed/", "en"),
    Source("Harpers", "https://harpers.co.uk/", "https://harpers.co.uk/rss", "en"),
    Source("The Grocer (Alcoholic Drinks)", "https://www.thegrocer.co.uk/alcoholic-drinks/41.subject", None, "en"),
    Source("ウイスキーディスティラリー情報", "https://whisky-distillery.info/", "https://whisky-distillery.info/feed/", "ja"),
    Source("Whisky777", "https://whisky777.com/", "https://whisky777.com/feed/", "ja"),
    Source("Whisky Magazine", "https://whiskymag.com/", "https://whiskymag.com/feed/", "en"),
    Source("Whisky Advocate", "https://www.whiskyadvocate.com/", "https://www.whiskyadvocate.com/feed/", "en"),
    Source("日本洋酒酒造組合", "https://www.yoshu.or.jp/", None, "ja"),
]


GOOGLE_NEWS_QUERIES: list[dict] = [
    {"q": "ウイスキー", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ジャパニーズウイスキー", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "シングルモルト", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 蒸留所", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 新発売", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 限定", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "缶ハイボール", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "大麦 ウイスキー", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 売上", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 出荷", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 業績", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 市場", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 樽 熟成", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "ウイスキー 蒸留", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"q": "whisky", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "single malt", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "scotch whisky", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "Irish whiskey", "hl": "en", "gl": "IE", "ceid": "IE:en"},
    {"q": "Japanese whisky", "hl": "en", "gl": "US", "ceid": "US:en"},
    {"q": "bourbon whiskey", "hl": "en", "gl": "US", "ceid": "US:en"},
    {"q": "whisky distillery", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "Kavalan whisky", "hl": "en", "gl": "US", "ceid": "US:en"},
    {"q": "Indian single malt", "hl": "en", "gl": "US", "ceid": "US:en"},
    {"q": "World Whisky Day", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky acquisition", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "scotch whisky exports", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky sales market", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky revenue earnings", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "Diageo whisky results", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky distillation technology", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky maturation cask innovation", "hl": "en", "gl": "GB", "ceid": "GB:en"},
    {"q": "whisky yeast fermentation research", "hl": "en", "gl": "GB", "ceid": "GB:en"},
]
