"""调度主循环：把队列、抓取、解析、存储串起来。

线程分工（这是本文件最需要理解的地方）：
  - 调度线程（调用 run() 的那个）：出队、写库、改统计、把新链接入队；
  - 线程池里的 N 个 worker：robots 判定、限速等待、HTTP、解析。

为什么写库和入队只放在调度线程：SQLite 连接和 Frontier 都不是线程安全的，
集中在一个线程就完全不用加锁。worker 只做"输入→输出"，返回 WorkResult，
不碰共享状态。
"""

import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .config import CrawlConfig
from .fetcher import Fetcher
from .frontier import Frontier
from .models import FetchResult, Page, Stats, Task
from .parser import Parser
from .ratelimit import DomainRateLimiter
from .robots import RobotsCache
from .storage import Storage
from .url_utils import host_of, normalize_url, should_visit

log = logging.getLogger(__name__)


@dataclass
class WorkResult:
    """一个 worker 干完活的产物，交回调度线程处理。"""

    task: Task
    fetch: FetchResult | None = None
    page: Page | None = None
    links: list[str] = field(default_factory=list)
    blocked: bool = False


class CrawlEngine:
    def __init__(
        self,
        cfg: CrawlConfig,
        *,
        storage: Storage | None = None,
        robots: RobotsCache | None = None,
        fetcher_factory=None,
        event_queue=None,
    ):
        ok, message = cfg.validate()
        if not ok:
            raise ValueError(message)

        self.cfg = cfg
        self.storage = storage or Storage(cfg.db_path)
        self.robots = robots or RobotsCache(cfg.user_agent, enabled=cfg.respect_robots)
        self.limiter = DomainRateLimiter(cfg.interval)
        self.frontier = Frontier(cfg.strategy)
        self.parser = Parser()
        self.stats = Stats()
        self.events = event_queue

        # 测试时可以换成假抓取器，正式运行时用真的 Fetcher
        self._fetcher_factory = fetcher_factory or (lambda config: Fetcher(config))
        self._thread_local = threading.local()

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None
        self._pool: ThreadPoolExecutor | None = None
        self._inflight: set = set()
        self._started_at = 0.0

    # ---- 对外控制 ----

    def start(self) -> None:
        """后台起一个线程跑，立刻返回（界面用这个）。"""
        if self.is_running:
            return
        self._thread = threading.Thread(target=self.run, name="crawl-engine", daemon=True)
        self._thread.start()

    def run(self) -> None:
        """阻塞式跑完（命令行用这个）。"""
        self._prepare()
        try:
            while not self._stop.is_set():
                if self._pause.is_set():
                    time.sleep(0.1)
                    continue
                # 在飞的任务也算进去，否则 4 个 worker 会一起突破页数上限
                if self.stats.fetched + len(self._inflight) >= self.cfg.max_pages:
                    log.info("达到页数上限 %s，收尾", self.cfg.max_pages)
                    break
                task = self.frontier.pop()
                if task is None:
                    if not self._inflight:
                        break
                    self._drain(block=True)
                    continue
                self._submit(task)
                if len(self._inflight) >= self.cfg.workers:
                    self._drain(block=True)
            self._drain(block=True)
        finally:
            self._shutdown()

    def pause(self) -> None:
        self._pause.set()
        self._emit("state", "paused")

    def resume(self) -> None:
        self._pause.clear()
        self._emit("state", "running")

    def request_stop(self) -> None:
        """只发停止信号，不等线程结束。界面用这个，避免主线程被 join 卡住。"""
        self._stop.set()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def snapshot(self) -> dict:
        """给界面用的统计快照。"""
        self.stats.queued = len(self.frontier)
        return asdict(self.stats)

    # ---- 内部：准备与收尾 ----

    def _prepare(self) -> None:
        self._started_at = time.monotonic()
        self._pool = ThreadPoolExecutor(max_workers=self.cfg.workers, thread_name_prefix="crawl")
        for seed in self.cfg.seeds:
            url = normalize_url(seed)
            if url:
                self.frontier.push(Task(url=url, depth=0))
        log.info("开始爬取：种子 %s 个，策略 %s，上限 %s 页",
                 len(self.cfg.seeds), self.cfg.strategy, self.cfg.max_pages)
        self._emit("state", "running")

    def _shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        self.storage.commit()
        elapsed = time.monotonic() - self._started_at
        log.info("爬取结束：成功 %s，失败 %s，PDF %s，去重 %s，用时 %.1fs",
                 self.stats.fetched, self.stats.failed, self.stats.pdf,
                 self.frontier.dup, elapsed)
        self._emit("done", self.snapshot())
        self._emit("state", "finished")

    # ---- 内部：调度 ----

    def _submit(self, task: Task) -> None:
        future = self._pool.submit(self._process, task)
        self._inflight.add(future)

    def _drain(self, block: bool) -> None:
        """收掉已经完成的 worker 结果。"""
        if not self._inflight:
            return
        done, _ = wait(
            self._inflight,
            timeout=None if block else 0.2,
            return_when=FIRST_COMPLETED,
        )
        for future in done:
            self._inflight.discard(future)
            self._collect(future)

    # ---- 内部：worker 侧 ----

    def _process(self, task: Task) -> WorkResult:
        """在 worker 线程里执行：判定 robots → 限速 → 抓取 → 解析。"""
        if self._stop.is_set():
            return WorkResult(task)

        if not self.robots.allowed(task.url):
            return WorkResult(task, blocked=True)

        host = host_of(task.url)
        self.limiter.wait(host)

        fetch = self._fetcher().fetch(task.url)
        page, links = None, []
        if fetch.kind == "html" and fetch.html:
            page, links = self.parser.parse(fetch.html, task.url)
        return WorkResult(task, fetch=fetch, page=page, links=links)

    def _fetcher(self) -> Fetcher:
        """每个线程一个 Fetcher：requests.Session 不是线程安全的。"""
        fetcher = getattr(self._thread_local, "fetcher", None)
        if fetcher is None:
            fetcher = self._fetcher_factory(self.cfg)
            self._thread_local.fetcher = fetcher
        return fetcher

    # ---- 内部：调度侧（只有这里能改状态） ----

    def _collect(self, future) -> None:
        try:
            result = future.result()
        except Exception as exc:                        # worker 里不该漏出来的兜底
            log.error("任务异常：%s", exc)
            self.stats.failed += 1
            return

        if result.blocked:
            self.stats.blocked += 1
            log.info("robots 拒绝 %s", result.task.url)
            return

        fetch = result.fetch
        if fetch is None:                               # 停止时提前返回的空结果
            return

        if fetch.kind == "error":
            self.stats.failed += 1
            log.warning("抓取失败 %s (%s)", fetch.url, fetch.error)
            return
        if fetch.kind == "pdf":
            self.stats.pdf += 1
            self.storage.save_pdf(fetch.url, result.task.parent or "", result.task.anchor, result.task.depth)
            log.info("PDF %s", fetch.url)
            return
        if fetch.kind == "other":
            self.stats.skipped += 1
            log.debug("跳过非 HTML %s", fetch.url)
            return

        self._store_page(result, fetch)
        self._enqueue_links(result)

    def _store_page(self, result: WorkResult, fetch: FetchResult) -> None:
        page = result.page
        page.http_status = fetch.status
        page.elapsed_ms = fetch.elapsed_ms
        page.depth = result.task.depth
        page.parent_url = result.task.parent or ""
        page.fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        page.content_type = fetch.content_type
        self.stats.bytes += len(fetch.html or "")

        inserted = self.storage.save(page)
        if not inserted:
            # 库里已经有这个 URL（比如重跑同一批），不算失败也不算新增
            self.stats.dup += 1
            log.debug("已存在，跳过 %s", page.url)
            return
        if page.ok:
            self.stats.fetched += 1
        else:
            self.stats.failed += 1
        log.info("抓取成功 %s 深度=%s 耗时=%sms", page.url, page.depth, page.elapsed_ms)
        self._emit("page", {"url": page.url, "title": page.title,
                            "publish_date": page.publish_date, "site": page.site})
        self._emit("stats", self.snapshot())

    def _enqueue_links(self, result: WorkResult) -> None:
        anchor_host = host_of(result.task.url)
        child_depth = result.task.depth + 1
        for raw in result.links:
            url = normalize_url(raw)
            if not url:
                continue
            allowed, reason = should_visit(url, child_depth, self.cfg, anchor_host)
            if not allowed:
                log.debug("过滤链接 %s (%s)", url, reason)
                continue
            task = Task(url=url, depth=child_depth, parent=result.task.url)
            if not self.frontier.push(task):
                self.stats.dup += 1

    def _emit(self, kind: str, data) -> None:
        """给界面发事件；没有界面（命令行）时就是空操作。"""
        if self.events is not None:
            self.events.put({"type": kind, "data": data})
