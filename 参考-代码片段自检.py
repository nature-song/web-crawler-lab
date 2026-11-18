"""临时自检：验证规划文档里的代码片段可运行、结论正确。"""
import collections
import heapq
import itertools
import posixpath
import re
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode

# ---------- 5.1 URL 规范化 ----------
DROP_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
               "utm_content", "spm", "from", "share_token", "sessionid", "sid"}
DEFAULT_PORT = {"http": 80, "https": 443}


def normalize_url(raw: str, base: str | None = None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw == "#" or raw.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return None
    try:
        url = urljoin(base, raw) if base else raw
        p = urlsplit(url)
        port = p.port
    except ValueError:
        return None

    scheme = p.scheme.lower()
    if scheme not in ("http", "https"):
        return None
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        return None

    netloc = host if port in (None, DEFAULT_PORT[scheme]) else f"{host}:{port}"

    path = posixpath.normpath(p.path or "/")
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if k.lower() not in DROP_PARAMS)
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


cases = [
    ("HTTP://Example.COM:80/a/../b/?utm_source=x&b=2&a=1#top", None,
     "http://example.com/b?a=1&b=2"),
    ("/x#top", "http://127.0.0.1:8000/", "http://127.0.0.1:8000/x"),
    ("../news/p1.html", "http://127.0.0.1:8000/a/b/index.html",
     "http://127.0.0.1:8000/a/news/p1.html"),
    ("https://A.com:443/x/", None, "https://a.com/x"),
    ("javascript:void(0)", None, None),
    ("mailto:a@b.com", None, None),
    ("#", None, None),
    ("ftp://a.com/x", None, None),
    ("http://a.com", None, "http://a.com/"),
    ("http://a.com//x///y", None, "http://a.com/x/y"),
]
for raw, base, want in cases:
    got = normalize_url(raw, base)
    assert got == want, f"\n raw={raw!r} base={base!r}\n got={got!r}\n want={want!r}"
print("normalize_url: 10/10 通过")


# ---------- 5.3 Frontier ----------
class Task:
    def __init__(self, url, depth=0, parent=None, anchor="", priority=0.0):
        self.url, self.depth, self.parent = url, depth, parent
        self.anchor, self.priority = anchor, priority


class Frontier:
    def __init__(self, strategy="bfs"):
        assert strategy in ("bfs", "dfs", "best")
        self.strategy = strategy
        self._dq = collections.deque()
        self._heap = []
        self._seq = itertools.count()
        self._seen = set()
        self.pushed = self.dup = 0

    def push(self, task) -> bool:
        if task.url in self._seen:
            self.dup += 1
            return False
        self._seen.add(task.url)
        self.pushed += 1
        if self.strategy == "best":
            heapq.heappush(self._heap, (-task.priority, next(self._seq), task))
        else:
            self._dq.append(task)
        return True

    def pop(self):
        if self.strategy == "best":
            return heapq.heappop(self._heap)[2] if self._heap else None
        if not self._dq:
            return None
        return self._dq.popleft() if self.strategy == "bfs" else self._dq.pop()

    def __len__(self):
        return len(self._heap) if self.strategy == "best" else len(self._dq)


bfs, dfs, best = Frontier("bfs"), Frontier("dfs"), Frontier("best")
for name, f in (("a", bfs), ("b", bfs), ("c", bfs)):
    f.push(Task(name))
assert [bfs.pop().url, bfs.pop().url, bfs.pop().url] == ["a", "b", "c"]
for name, f in (("a", dfs), ("b", dfs), ("c", dfs)):
    f.push(Task(name))
assert [dfs.pop().url, dfs.pop().url, dfs.pop().url] == ["c", "b", "a"]
for name, pr in (("a", 1.0), ("b", 5.0), ("c", 3.0)):
    best.push(Task(name, priority=pr))
assert [best.pop().url, best.pop().url, best.pop().url] == ["b", "c", "a"]
d = Frontier("bfs")
d.push(Task("x")); d.push(Task("x"))
assert d.dup == 1 and len(d) == 1
print("Frontier: BFS/DFS/Best + 去重 全通过")


# ---------- 5.4 robots 通配符 ----------
def _to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    body = re.escape(pattern).replace(r"\*", ".*")
    return re.compile("^" + body + ("$" if anchored else ".*"))


r1 = _to_regex("/admin/*")
assert r1.match("/admin/secret.html") and r1.match("/admin/")
assert not r1.match("/public/x")
r2 = _to_regex("/x.php$")
assert r2.match("/x.php") and not r2.match("/x.php?a=1")
print("robots 通配符匹配: 通过")


# ---------- 5.5 限速 ----------
import threading


class DomainRateLimiter:
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._last.get(host, 0.0) + self.delay)
            self._last[host] = slot
        delta = slot - time.monotonic()
        if delta > 0:
            time.sleep(delta)


rl = DomainRateLimiter(0.2)
t0 = time.monotonic()
for _ in range(3):
    rl.wait("a.com")
elapsed = time.monotonic() - t0
assert 0.38 <= elapsed <= 0.55, elapsed
t0 = time.monotonic()
rl.wait("b.com")   # 不同域不等待
assert time.monotonic() - t0 < 0.05
print(f"限速: 3 次同域耗时 {elapsed:.2f}s（期望≈0.4s），跨域不阻塞 通过")


# ---------- 5.7 抽取 ----------
from bs4 import BeautifulSoup

DATE_RE = re.compile(r"(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})")
TITLE_CHAIN = ["citation_title", "og:title", "twitter:title", "dc.title"]
DATE_CHAIN = ["citation_publication_date", "article:published_time", "dc.date"]
ABSTRACT_CHAIN = ["citation_abstract", "description", "og:description"]
KEYWORD_CHAIN = ["citation_keywords", "keywords", "news_keywords"]


def _meta_map(soup) -> dict[str, str]:
    m: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").strip().lower()
        val = (tag.get("content") or "").strip()
        if key and val:
            m.setdefault(key, val)
    return m


def extract(html: str, url: str, base: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    meta = _meta_map(soup)
    title = next((meta[k] for k in TITLE_CHAIN if meta.get(k)), "") \
        or (soup.h1.get_text(strip=True) if soup.h1 else "") \
        or (soup.title.get_text(strip=True) if soup.title else "")
    authors = "; ".join(sorted({a.strip() for a in
                                re.split(r"[,;，；、]| and ", meta.get("citation_author", "")) if a.strip()}))
    date = ""
    for k in DATE_CHAIN:
        if meta.get(k):
            m = DATE_RE.search(meta[k])
            if m:
                date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                break
    if not date:
        m = DATE_RE.search(soup.get_text(" ", strip=True)[:3000])
        if m:
            date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    abstract = next((meta[k] for k in ABSTRACT_CHAIN if meta.get(k)), "")
    keywords = meta.get("citation_keywords", "") or meta.get("keywords", "")
    return {"url": url, "title": title[:300], "authors": authors,
            "abstract": abstract[:1000], "keywords": keywords,
            "publish_date": date, "site": base}


html = """<html><head>
<meta name="citation_title" content="基于深度学习的网络流量识别">
<meta name="citation_author" content="张三, 李四">
<meta name="citation_publication_date" content="2025/03/14">
<meta name="citation_keywords" content="流量识别; 深度学习">
<meta name="description" content="本文提出一种方法……">
</head><body><h1>备选标题</h1></body></html>"""
rec = extract(html, "http://x.org/a", "x.org")
assert rec["title"] == "基于深度学习的网络流量识别", rec
assert rec["authors"] == "张三; 李四", rec
assert rec["publish_date"] == "2025-03-14", rec
assert rec["keywords"] == "流量识别; 深度学习"
print("字段抽取: 4/4 通过")

html2 = "<html><body><h1>只有一级标题</h1><p>发布于 2024年7月9日</p></body></html>"
rec2 = extract(html2, "http://x.org/b", "x.org")
assert rec2["title"] == "只有一级标题" and rec2["publish_date"] == "2024-07-09", rec2
print("兜底抽取: 通过（h1 + 正文日期正则）")

print("\n全部自检通过 ✅")
