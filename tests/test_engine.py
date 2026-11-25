import queue

import pytest

from crawler.config import CrawlConfig
from crawler.engine import CrawlEngine
from crawler.logger import setup_logger
from crawler.models import FetchResult
from crawler.robots import RobotsCache
from crawler.storage import Storage

BASE = "http://test.local"


@pytest.fixture(autouse=True)
def quiet_logger(tmp_path):
    setup_logger(tmp_path / "test.log", console=False)


def html(*hrefs):
    links = "".join(f'<a href="{href}">链接</a>' for href in hrefs)
    return f"<html><head><title>页面</title></head><body>{links}</body></html>"


def make_fetcher(route):
    """用字典模拟一个站点：url -> HTML 字符串 / FetchResult / 不存在。"""

    class FakeFetcher:
        def __init__(self, cfg):
            self.cfg = cfg

        def fetch(self, url):
            item = route.get(url)
            if item is None:
                return FetchResult(url, "error", 404, error="HTTP 404")
            if isinstance(item, FetchResult):
                return item
            return FetchResult(url, "html", 200, html=item, content_type="text/html")

    return lambda cfg: FakeFetcher(cfg)


@pytest.fixture
def build(tmp_path):
    created = []

    def _build(route, robots_text="", **overrides):
        data = {
            "seeds": [f"{BASE}/"],
            "workers": 1,
            "interval": 0.1,
            "db_path": str(tmp_path / "crawl.db"),
            "log_path": str(tmp_path / "crawl.log"),
        }
        data.update(overrides)
        cfg = CrawlConfig(**data)
        storage = Storage(cfg.db_path)
        created.append(storage)
        robots = RobotsCache(cfg.user_agent, fetch_text=lambda url: robots_text)
        engine = CrawlEngine(
            cfg,
            storage=storage,
            robots=robots,
            fetcher_factory=make_fetcher(route),
        )
        return engine, storage

    yield _build

    for storage in created:
        storage.close()


def test_crawl_small_graph(build):
    route = {
        f"{BASE}/": html("/a", "/b"),
        f"{BASE}/a": html("/c"),
        f"{BASE}/b": html(),
        f"{BASE}/c": html(),
    }
    engine, storage = build(route)
    engine.run()

    assert engine.stats.fetched == 4
    assert storage.count() == 4
    assert engine.stats.failed == 0


def test_depth_limit(build):
    route = {
        f"{BASE}/": html("/a"),
        f"{BASE}/a": html("/c"),
        f"{BASE}/c": html(),
    }
    engine, _ = build(route, max_depth=1)
    engine.run()
    assert engine.stats.fetched == 2


def test_max_pages(build):
    route = {f"{BASE}/": html("/a", "/b", "/c")}
    for name in "abc":
        route[f"{BASE}/{name}"] = html()
    engine, _ = build(route, max_pages=2)
    engine.run()
    assert engine.stats.fetched == 2


def test_robots_blocks_secret_path(build):
    route = {
        f"{BASE}/": html("/open", "/secret"),
        f"{BASE}/open": html(),
        f"{BASE}/secret": html(),
    }
    engine, _ = build(route, robots_text="User-agent: *\nDisallow: /secret\n")
    engine.run()

    assert engine.stats.blocked == 1
    assert engine.stats.fetched == 2


def test_pdf_is_recorded_separately(build):
    route = {
        f"{BASE}/": html("/doc.pdf"),
        f"{BASE}/doc.pdf": FetchResult(f"{BASE}/doc.pdf", "pdf", 200,
                                       content_type="application/pdf"),
    }
    engine, storage = build(route)
    engine.run()

    assert engine.stats.pdf == 1
    assert storage.count_pdf() == 1
    assert storage.count() == 1          # 只有首页进了 pages 表


def test_error_is_counted_not_fatal(build):
    route = {f"{BASE}/": html("/missing")}
    engine, _ = build(route)
    engine.run()

    assert engine.stats.failed == 1
    assert engine.stats.fetched == 1


def test_duplicate_link_counted(build):
    route = {f"{BASE}/": html("/a", "/a?utm_source=x"), f"{BASE}/a": html()}
    engine, storage = build(route)
    engine.run()

    assert engine.stats.dup == 1
    assert storage.count() == 2


def test_events_are_emitted(build):
    events = queue.Queue()
    route = {f"{BASE}/": html()}
    engine, _ = build(route)
    engine.events = events
    engine.run()

    kinds = []
    while not events.empty():
        kinds.append(events.get_nowait()["type"])
    assert "page" in kinds
    assert "stats" in kinds
    assert "done" in kinds


def test_stop_before_run(build):
    route = {f"{BASE}/": html()}
    engine, storage = build(route)
    engine.stop()
    engine.run()
    assert engine.stats.fetched == 0
    assert storage.count() == 0


def test_rerun_counts_duplicates(build):
    route = {f"{BASE}/": html()}
    engine, storage = build(route)
    engine.run()

    engine_again, _ = build(route)      # 同一个库文件，模拟重复跑同一批
    engine_again.run()

    assert engine.stats.fetched == 1
    assert engine_again.stats.fetched == 0
    assert engine_again.stats.dup == 1
    assert storage.count() == 1

def test_crawl_delay_from_robots_is_applied(build):
    route = {f"{BASE}/": html()}
    engine, _ = build(route, robots_text="User-agent: *\nCrawl-delay: 2\n")
    engine.run()
    assert engine.limiter.interval_for("test.local") == 2.0


def test_429_slows_down_domain(build):
    route = {f"{BASE}/": FetchResult(f"{BASE}/", "error", 429, error="HTTP 429")}
    engine, _ = build(route)
    engine.run()
    assert engine.limiter.interval_for("test.local") > engine.cfg.interval


def test_crawl_log_records_lifecycle(build):
    route = {f"{BASE}/": html()}
    engine, storage = build(route)
    engine.run()
    assert storage.count_log() >= 2
