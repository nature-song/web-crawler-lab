"""URL 规范化、同域判断和抓取范围过滤。"""

import posixpath
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .config import CrawlConfig

# 只影响来源统计，不改变页面内容
DROP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "spm", "from", "share_token", "sessionid", "sid",
}

# 抓到也没法解析的类型，直接跳过。pdf 不在此列，要单独记录
BAD_SUFFIX = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf",
    ".zip", ".rar", ".7z", ".gz", ".exe", ".msi",
    ".mp3", ".mp4", ".avi", ".mov",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
)

DEFAULT_PORT = {"http": 80, "https": 443}


def normalize_url(raw: str, base: str | None = None) -> str | None:
    """统一成唯一形式。不值得抓的（非 http、纯锚点等）返回 None。"""
    if not raw:
        return None
    raw = raw.strip()
    if raw == "#" or raw.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return None

    try:
        url = urljoin(base, raw) if base else raw
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return None

    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return None

    netloc = host if port in (None, DEFAULT_PORT[scheme]) else f"{host}:{port}"

    path = posixpath.normpath(parts.path or "/")
    if path.startswith("//"):          # normpath 会保留开头的双斜杠
        path = "/" + path.lstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in DROP_PARAMS
    )
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_pdf(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".pdf")


def should_visit(url: str, depth: int, cfg: CrawlConfig, seed_host: str) -> tuple[bool, str]:
    """返回 (是否抓取, 跳过原因)。原因会进日志和统计，别省。"""
    if depth > cfg.max_depth:
        return False, "depth"
    if url.lower().split("?", 1)[0].endswith(BAD_SUFFIX):
        return False, "suffix"
    if cfg.same_domain and host_of(url) != seed_host:
        return False, "offsite"
    return True, ""
