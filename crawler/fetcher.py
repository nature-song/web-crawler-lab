"""HTTP 抓取：超时、重试、编码识别、内容类型判定。

对外只有一个方法 fetch()，它**不抛异常**——所有网络问题都变成
FetchResult(kind="error")，这样引擎的调度循环里不用写 try/except 套娃。

注意 Session 不是线程安全的，所以每个工作线程要各自持有一个 Fetcher 实例；
Fetcher 的构造函数允许注入 session，测试时传一个假对象就能离线跑。
"""

import logging
import time

import requests

from .config import CrawlConfig
from .models import FetchResult
from .url_utils import is_pdf

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024        # 单页最大读取量，超过就放弃，防止被超大文件拖死
HTML_TYPES = ("text/html", "application/xhtml+xml")
RETRY_STATUS = (429, 500, 502, 503, 504)
# requests 在响应头没写 charset 时会把编码设成 ISO-8859-1，这个值等于"没声明"，
# 不能拿来解码，否则中文全变乱码
FAKE_ENCODINGS = ("iso-8859-1", "ascii")


def decode(raw: bytes, declared: str | None = None) -> str:
    """按 声明编码 → utf-8 → gb18030 的顺序尝试解码。

    用严格模式逐个试，失败了才换下一个，这样"GBK 页面被当成 UTF-8"能自动纠正。
    """
    candidates: list[str] = []
    if declared and declared.lower() not in FAKE_ENCODINGS:
        candidates.append(declared)
    candidates += ["utf-8", "gb18030"]

    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(self, cfg: CrawlConfig, session: requests.Session | None = None):
        self.cfg = cfg
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = cfg.user_agent

    def fetch(self, url: str) -> FetchResult:
        """抓一个 URL，网络异常不向外抛。"""
        attempts = max(1, self.cfg.retries)
        last_error = ""

        for attempt in range(attempts):
            started = time.monotonic()
            try:
                resp = self.session.get(
                    url, timeout=self.cfg.timeout, stream=True, allow_redirects=True
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)      # 1s、2s、4s 退避
                    continue
                break

            if resp.status_code in RETRY_STATUS and attempt < attempts - 1:
                resp.close()
                last_error = f"HTTP {resp.status_code}"
                time.sleep(2 ** attempt)
                continue

            return self._build(url, resp, started)

        log.warning("抓取失败 url=%s err=%s", url, last_error)
        return FetchResult(url=url, kind="error", error=last_error or "重试次数用尽")

    def _build(self, url: str, resp, started: float) -> FetchResult:
        """根据状态码和 Content-Type 决定这一页怎么处理。"""
        elapsed = int((time.monotonic() - started) * 1000)
        status = resp.status_code
        ctype = (resp.headers.get("Content-Type") or "").lower()

        try:
            if status >= 400:
                return FetchResult(url, "error", status, content_type=ctype,
                                   elapsed_ms=elapsed, error=f"HTTP {status}")

            if is_pdf(url) or "application/pdf" in ctype:
                return FetchResult(url, "pdf", status, content_type=ctype,
                                   elapsed_ms=elapsed)

            if not any(t in ctype for t in HTML_TYPES):
                return FetchResult(url, "other", status, content_type=ctype,
                                   elapsed_ms=elapsed, error="非 HTML 类型")

            raw = self._read_capped(resp)
            if raw is None:
                return FetchResult(url, "other", status, content_type=ctype,
                                   elapsed_ms=elapsed, error="页面过大")
            return FetchResult(url, "html", status, html=decode(raw, resp.encoding),
                               content_type=ctype, elapsed_ms=elapsed)
        finally:
            resp.close()

    def _read_capped(self, resp) -> bytes | None:
        """分块读，超过 MAX_BYTES 就返回 None。"""
        chunks: list[bytes] = []
        size = 0
        for chunk in resp.iter_content(16 * 1024):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                return None
        return b"".join(chunks)
