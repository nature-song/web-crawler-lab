"""各模块共享的数据结构。

单独放一个文件，是为了避免 engine、fetcher、parser 之间互相 import 造成循环依赖：
大家都只依赖 models，models 不依赖任何人。
"""

from dataclasses import dataclass


@dataclass(slots=True)
class Task:
    """队列里的一个待抓任务。"""

    url: str
    depth: int = 0                 # 距种子的层数，用来做深度限制
    parent: str | None = None      # 从哪个页面发现它的，方便追溯
    anchor: str = ""               # 锚文本，最佳优先算相关性会用到
    priority: float = 0.0          # 只有 best 策略才看这个值


@dataclass(slots=True)
class Page:
    """解析出来的一页结果，字段和数据库 pages 表一一对应。"""

    url: str
    title: str = ""
    authors: str = ""
    abstract: str = ""
    keywords: str = ""
    publish_date: str = ""         # 统一成 YYYY-MM-DD，取不到就留空
    site: str = ""
    content_type: str = ""
    http_status: int = 0
    depth: int = 0
    parent_url: str = ""
    fetched_at: str = ""
    elapsed_ms: int = 0
    ok: bool = True                # 解析成功与否，失败的页面也要留下来
    error: str = ""


@dataclass(slots=True)
class FetchResult:
    """一次抓取的产物。

    kind 用字符串而不是异常，是为了让引擎主循环只有 if/else 两条分支，
    不用到处写 try/except。
    """

    url: str
    kind: str                      # html | pdf | other | error
    status: int = 0
    html: str | None = None
    content_type: str = ""
    elapsed_ms: int = 0
    error: str = ""


@dataclass
class Stats:
    """界面顶部那排数字。由调度线程单独修改，所以不用加锁。"""

    fetched: int = 0               # 成功入库的页面数
    failed: int = 0                # 最终失败的请求数
    dup: int = 0                   # 被去重挡下的 URL 数
    blocked: int = 0               # robots 拒绝的 URL 数
    skipped: int = 0               # 后缀/类型不符被跳过的数
    pdf: int = 0                   # 识别到的 PDF 链接数
    queued: int = 0                # 队列里还剩多少
    bytes: int = 0                 # 累计下载字节
