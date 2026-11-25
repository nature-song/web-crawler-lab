"""HTML 解析：把一页 HTML 变成 Page 对象，顺便把页面里的链接捞出来。

抽取走三级兜底：
  1. meta 元数据（citation_* / og:* / dc.*）—— 学术库、新闻站基本都有，最准；
  2. DOM 结构（h1、title、time[datetime]）—— 普通页面；
  3. 正则（正文前 3000 字里找日期）—— 什么标记都没有的老页面。

本模块只负责"从 HTML 里取信息"，不发请求、不去重、不判断深度；
那些是 fetcher 和 engine 的职责。
"""

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .models import Page

try:                          # lxml 快很多，没装也能跑，只是慢一点
    import lxml  # noqa: F401

    _HTML_PARSER = "lxml"
except ImportError:
    _HTML_PARSER = "html.parser"


# 每个字段的候选 meta 名称，从上往下依次尝试
TITLE_KEYS = ("citation_title", "og:title", "twitter:title", "dc.title")
AUTHOR_KEYS = ("citation_author", "dc.creator", "author", "article:author")
DATE_KEYS = (
    "citation_publication_date",
    "article:published_time",
    "og:published_time",
    "dc.date",
    "pubdate",
    "publishdate",
)
ABSTRACT_KEYS = ("citation_abstract", "description", "og:description", "dc.description")
KEYWORD_KEYS = ("citation_keywords", "keywords", "news_keywords")

# 2025-03-14 / 2025/3/14 / 2025.3.14 / 2025年3月14日 都能匹配
DATE_RE = re.compile(r"((?:19|20)\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})")
# 多作者常见分隔：逗号、分号、顿号，以及英文 and
AUTHOR_SPLIT_RE = re.compile(r"[,;，；、]| and ")

MAX_AUTHORS = 200
MAX_KEYWORDS = 200


def _meta_index(soup) -> dict[str, list[str]]:
    """把页面里所有 <meta> 收成 {名称: [内容, ...]}。

    用列表而不是单个值，是因为 citation_author 这类字段会重复出现多次，
    每个作者一个标签，只取第一个会丢人。
    """
    index: dict[str, list[str]] = {}
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").strip().lower()
        content = (tag.get("content") or "").strip()
        if name and content:
            index.setdefault(name, []).append(content)
    return index


def _first_meta(index: dict[str, list[str]], keys: tuple[str, ...]) -> str:
    """按候选顺序找到第一个有值的 meta。"""
    for key in keys:
        values = index.get(key)
        if values:
            return values[0]
    return ""


def normalize_date(text: str) -> str:
    """把各种写法的日期统一成 YYYY-MM-DD，认不出来就返回空串。

    月和日会做范围检查，2025/13/40 这种明显是抽错了，宁可留空也不入库。
    """
    if not text:
        return ""
    match = DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = (int(part) for part in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _title(soup, index: dict[str, list[str]]) -> str:
    title = _first_meta(index, TITLE_KEYS)
    if title:
        return title
    for name in ("h1", "title"):      # 没有 meta 就退到页面标题
        tag = soup.find(name)
        if tag:
            text = tag.get_text(" ", strip=True)
            if text:
                return text
    return ""


def _authors(index: dict[str, list[str]]) -> str:
    """把所有作者名取出来、拆开、去重，用分号连起来。"""
    names: list[str] = []
    for key in AUTHOR_KEYS:
        for value in index.get(key, []):
            for part in AUTHOR_SPLIT_RE.split(value):
                part = part.strip()
                if part and part not in names:      # 保持原顺序去重
                    names.append(part)
        if names:                                # 找到一层就不再往下降级
            break
    return "; ".join(names)


def _first_text(soup, limit: int = 3000) -> str:
    """只拼前 limit 个字符的正文。

    直接用 soup.get_text() 会把整页（可能几 MB）先拼成一个字符串再切片，
    大页面上很浪费，所以边遍历边累计长度。
    """
    parts: list[str] = []
    size = 0
    for text in soup.stripped_strings:
        parts.append(text)
        size += len(text)
        if size >= limit:
            break
    return " ".join(parts)[:limit]


def _publish_date(soup, index: dict[str, list[str]]) -> str:
    for key in DATE_KEYS:
        for value in index.get(key, []):
            date = normalize_date(value)
            if date:
                return date

    for tag in soup.find_all("time"):            # <time datetime="2025-03-14">
        date = normalize_date(tag.get("datetime", "") or tag.get_text(" ", strip=True))
        if date:
            return date

    # 最后的兜底：正文开头常有"发布时间：2025-03-14"，只扫前 3000 字，别把整页翻一遍
    return normalize_date(_first_text(soup))


def _abstract(soup, index: dict[str, list[str]]) -> str:
    abstract = _first_meta(index, ABSTRACT_KEYS)
    if abstract:
        return abstract
    for tag in soup.find_all("p"):               # 没有 description 就拿第一段像正文的
        text = tag.get_text(" ", strip=True)
        if len(text) >= 30:
            return text
    return ""


class Parser:
    """解析器本身没有状态，用类只是为了让长度上限集中配置。"""

    def __init__(self, max_links: int = 200, max_title: int = 300, max_text: int = 1000):
        self.max_links = max_links
        self.max_title = max_title
        self.max_text = max_text

    def parse(self, html: str, url: str) -> tuple[Page, list[str]]:
        """返回 (页面对象, 绝对链接列表)。

        链接只做 urljoin 和协议过滤，不判断深度和域名——那是引擎的事。
        解析炸了不抛异常，返回 ok=False 的空页面，保证爬虫能继续跑。
        """
        site = (urlsplit(url).hostname or "").lower()
        try:
            soup = BeautifulSoup(html, _HTML_PARSER)
            index = _meta_index(soup)
            page = Page(
                url=url,
                title=_title(soup, index)[: self.max_title],
                authors=_authors(index)[:MAX_AUTHORS],
                abstract=_abstract(soup, index)[: self.max_text],
                keywords=_first_meta(index, KEYWORD_KEYS)[:MAX_KEYWORDS],
                publish_date=_publish_date(soup, index),
                site=site,
            )
            return page, self._links(soup, url)
        except Exception as exc:                 # 畸形 HTML 不该让整轮任务停下
            return Page(url=url, site=site, ok=False, error=f"{type(exc).__name__}: {exc}"), []

    def _links(self, soup, base_url: str) -> list[str]:
        """抽出可跳转的链接：补成绝对地址、去重、跳过 nofollow 和 javascript:。"""
        links: list[str] = []
        seen: set[str] = set()
        for tag in soup.find_all("a", href=True):
            rel = [item.lower() for item in (tag.get("rel") or [])]
            if "nofollow" in rel:                # 站长明确说别跟，就不跟
                continue
            href = tag["href"].strip()
            if not href or href.startswith("#"):
                continue
            url = urljoin(base_url, href)
            if urlsplit(url).scheme not in ("http", "https"):
                continue
            if url in seen:
                continue
            seen.add(url)
            links.append(url)
            if len(links) >= self.max_links:
                break
        return links
