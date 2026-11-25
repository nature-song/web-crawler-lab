"""爬取参数集中放一处，避免魔法数字散落在各个模块。"""

from dataclasses import dataclass, field


@dataclass
class CrawlConfig:
    seeds: list[str] = field(default_factory=list)
    strategy: str = "bfs"          # bfs | dfs | best
    max_depth: int = 3
    max_pages: int = 500
    interval: float = 1.0          # 秒 / 域名
    workers: int = 4
    timeout: float = 10.0
    retries: int = 3
    same_domain: bool = True
    respect_robots: bool = True
    user_agent: str = "CourseCrawler/1.0 (student project)"
    db_path: str = "data/crawl.db"
    log_path: str = "logs/crawl.log"

    def validate(self) -> tuple[bool, str]:
        """返回 (是否合法, 错误信息)。错误信息直接给界面弹窗用。"""
        if not self.seeds:
            return False, "至少要填一个种子 URL"
        if self.strategy not in ("bfs", "dfs", "best"):
            return False, f"策略只能是 bfs / dfs / best，当前是 {self.strategy}"
        if not 0 <= self.max_depth <= 10:
            return False, "最大深度需在 0~10 之间"
        if not 1 <= self.max_pages <= 10000:
            return False, "最大页数需在 1~10000 之间"
        if not 0.1 <= self.interval <= 10:
            return False, "请求间隔需在 0.1~10 秒之间"
        if not 1 <= self.workers <= 8:
            return False, "并发数需在 1~8 之间"
        if not 1 <= self.timeout <= 60:
            return False, "超时需在 1~60 秒之间"
        if not 0 <= self.retries <= 5:
            return False, "重试次数需在 0~5 之间"
        return True, ""
