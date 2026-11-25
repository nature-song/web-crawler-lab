"""robots.txt 的抓取、解析与缓存。

为什么不直接用标准库的 urllib.robotparser：
  1. 它的路径匹配就是 filename.startswith(self.path)，不支持 * 和 $ 通配符；
  2. 它自己的 read() 用 urlopen，没法设 User-Agent 和超时。
所以这里实现 RFC 9309 的一个子集：User-agent / Allow / Disallow / Crawl-delay，
匹配规则按"最长模式优先，长度相同则 Allow 优先"。

抓取失败的处理（也是 RFC 允许的两种做法之一）：
  - 4xx（含 404，站点没有 robots.txt）：视为没有任何限制；
  - 5xx 或网络错误：也放行，但记一条 warning。这个取舍写进报告的局限性里。
"""

import contextlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)


@dataclass
class Rule:
    allow: bool
    pattern: str
    _regex: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._regex = _compile(self.pattern)

    def matches(self, path: str) -> bool:
        return bool(self._regex.match(path))

    @property
    def weight(self) -> int:
        """模式的特异程度：去掉通配符后的长度。越长越具体。"""
        return len(self.pattern.replace("*", "").replace("$", ""))


@dataclass
class Group:
    """robots.txt 里一个 User-agent 段落及其规则。"""

    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    delay: float | None = None

    def applies_to(self, user_agent: str) -> bool:
        ua = user_agent.lower()
        return any(a == "*" or ua.startswith(a) for a in self.agents)


def _compile(pattern: str) -> re.Pattern:
    """把 /admin/*.php$ 这样的模式编译成正则。"""
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    body = re.escape(pattern).replace(r"\*", ".*")
    return re.compile("^" + body + ("$" if anchored else ""))


def parse_robots(text: str) -> list[Group]:
    """把 robots.txt 文本解析成段落列表。空行、注释、不认识的字段都跳过。"""
    groups: list[Group] = []
    current: Group | None = None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()

        if key == "user-agent":
            # 连续多个 User-agent 行属于同一组；一旦该组已经有规则，就是新的一组
            if current is None or current.rules:
                current = Group()
                groups.append(current)
            current.agents.append(value.lower())
        elif key in ("allow", "disallow"):
            if current is None:
                continue
            if key == "disallow" and not value:
                continue            # "Disallow:" 空值等于没有限制
            current.rules.append(Rule(key == "allow", value))
        elif key == "crawl-delay" and current is not None:
            with contextlib.suppress(ValueError):
                current.delay = float(value)
    return groups


def _path_of(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


class RobotsCache:
    """按 host 缓存解析结果，默认 1 小时过期。"""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 10.0,
        ttl: float = 3600.0,
        enabled: bool = True,
        fetch_text=None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.ttl = ttl
        self.enabled = enabled
        self._fetch_text = fetch_text or self._http_fetch
        self._cache: dict[str, tuple[list[Group], float]] = {}
        self._lock = threading.Lock()

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        groups = self._groups_for(url)
        if not groups:
            return True
        rules = self._rules_for(groups)
        if not rules:
            return True

        path = _path_of(url)
        hits = [r for r in rules if r.matches(path)]
        if not hits:
            return True
        # 最长模式胜出；一样长时 Allow 优先（RFC 9309 的约定）
        best = max(hits, key=lambda r: (r.weight, r.allow))
        return best.allow

    def delay_for(self, url: str) -> float | None:
        """robots.txt 里声明的 Crawl-delay，没有就返回 None。"""
        groups = self._groups_for(url)
        group = self._best_group(groups)
        if group is None or group.delay is None:
            return None
        return min(group.delay, 10.0)     # 防止站点写个 999 把你卡死

    # ---- 内部实现 ----

    def _groups_for(self, url: str) -> list[Group]:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host:
            return []
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(host)
            if cached and now < cached[1]:
                return cached[0]

        text = self._fetch_text(f"{parts.scheme}://{host}/robots.txt")
        groups = parse_robots(text) if text else []
        with self._lock:
            self._cache[host] = (groups, now + self.ttl)
        return groups

    def _rules_for(self, groups: list[Group]) -> list[Rule]:
        group = self._best_group(groups)
        return group.rules if group else []

    def _best_group(self, groups: list[Group]) -> Group | None:
        """UA 越具体越优先：CourseCrawler 段优先于 * 段。"""
        matched = [g for g in groups if g.applies_to(self.user_agent)]
        if not matched:
            return None
        return max(matched, key=lambda g: max((len(a) for a in g.agents), default=0))

    def _http_fetch(self, url: str) -> str | None:
        try:
            resp = requests.get(
                url, timeout=self.timeout, headers={"User-Agent": self.user_agent}
            )
        except requests.RequestException as exc:
            log.warning("robots 抓取失败，按放行处理: %s (%s)", url, exc)
            return None
        if resp.status_code >= 500:
            log.warning("robots 返回 %s，按放行处理: %s", resp.status_code, url)
            return None
        if resp.status_code >= 400:
            return ""            # 没有 robots.txt，等于没有限制
        return resp.text
