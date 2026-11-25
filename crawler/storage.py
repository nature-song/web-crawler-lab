"""SQLite 存取：建表、写页面、写 PDF 链接、查询、导出 CSV。

四个设计取舍（报告里也能用）：
  1. 单写者：只有调度线程写库。连接虽然是 check_same_thread=False，但外面还加了一把锁，
     多线程误用时不会直接炸，最多排队；
  2. 批量提交：每 20 条 commit 一次。逐条提交比批量慢几十倍，长跑时尤其明显；
  3. 幂等：url 上有 UNIQUE 约束，写入用 INSERT OR IGNORE，
     就算上层去重失效也不会产生重复行；
  4. 原始 HTML 不落盘，只存抽出来的字段——省空间，也避免版权问题。
"""

import csv
import hashlib
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .models import Page

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    url_hash     TEXT NOT NULL,
    title        TEXT DEFAULT '',
    authors      TEXT DEFAULT '',
    abstract     TEXT DEFAULT '',
    keywords     TEXT DEFAULT '',
    publish_date TEXT DEFAULT '',
    site         TEXT DEFAULT '',
    content_type TEXT DEFAULT '',
    http_status  INTEGER DEFAULT 0,
    depth        INTEGER DEFAULT 0,
    parent_url   TEXT DEFAULT '',
    fetched_at   TEXT DEFAULT '',
    elapsed_ms   INTEGER DEFAULT 0,
    ok           INTEGER DEFAULT 1,
    error        TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_pages_site ON pages(site);
CREATE INDEX IF NOT EXISTS idx_pages_date ON pages(publish_date);
CREATE INDEX IF NOT EXISTS idx_pages_ok   ON pages(ok);

CREATE TABLE IF NOT EXISTS pdf_links (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    url      TEXT NOT NULL UNIQUE,
    found_on TEXT,
    anchor   TEXT,
    depth    INTEGER DEFAULT 0,
    found_at TEXT
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    level      TEXT,
    url        TEXT,
    event      TEXT,
    detail     TEXT,
    elapsed_ms INTEGER DEFAULT 0
);
"""

# 查出来给界面用、也用来定 CSV 表头的列，顺序保持一致
COLUMNS = (
    "url", "title", "authors", "abstract", "keywords", "publish_date",
    "site", "content_type", "http_status", "depth", "parent_url",
    "fetched_at", "elapsed_ms", "ok", "error",
)

_PAGE_FIELDS = COLUMNS + ("url_hash",)
_INSERT_PAGE = (
    f"INSERT OR IGNORE INTO pages ({', '.join(_PAGE_FIELDS)}) "
    f"VALUES ({', '.join(['?'] * len(_PAGE_FIELDS))})"
)


class Storage:
    BATCH_SIZE = 20

    def __init__(self, db_path: str | Path = "data/crawl.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()      # 所有写操作都过这把锁
        self._pending = 0                  # 还没 commit 的条数
        self._closed = False
        self.init_schema()

    def init_schema(self) -> None:
        """建表。IF NOT EXISTS，所以重复调用是安全的。"""
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- 写入 ----

    def save(self, page: Page) -> bool:
        """写一页。URL 已存在时返回 False（被忽略），新写入返回 True。"""
        values = tuple(getattr(page, column) if column != "ok" else int(page.ok) for column in COLUMNS)
        url_hash = hashlib.sha1(page.url.encode("utf-8")).hexdigest()

        with self._lock:
            cursor = self.conn.execute(_INSERT_PAGE, values + (url_hash,))
            self._pending += 1
            if self._pending >= self.BATCH_SIZE:
                self.conn.commit()
                self._pending = 0
        return cursor.rowcount > 0

    def save_many(self, pages) -> int:
        """批量写，返回真正新增的条数。"""
        return sum(1 for page in pages if self.save(page))

    def save_pdf(self, url: str, found_on: str = "", anchor: str = "", depth: int = 0) -> bool:
        with self._lock:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO pdf_links (url, found_on, anchor, depth, found_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (url, found_on, anchor, depth, _now()),
            )
            self._pending += 1
            if self._pending >= self.BATCH_SIZE:
                self.conn.commit()
                self._pending = 0
        return cursor.rowcount > 0

    def commit(self) -> None:
        """把没提交的攒批一起落盘。界面点"停止"时要调一次。"""
        with self._lock:
            self.conn.commit()
            self._pending = 0

    # ---- 查询与导出 ----

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    def count_pdf(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM pdf_links").fetchone()[0]

    def query(
        self,
        limit: int | None = 500,
        site: str = "",
        keyword: str = "",
        ok_only: bool = False,
    ) -> list[dict]:
        """按条件查结果，返回 dict 列表，界面表格直接拿这个填。"""
        sql = f"SELECT {', '.join(COLUMNS)} FROM pages WHERE 1=1"
        params: list = []
        if site:
            sql += " AND site = ?"
            params.append(site)
        if ok_only:
            sql += " AND ok = 1"
        if keyword:
            sql += " AND (title LIKE ? OR abstract LIKE ?)"
            params += [f"%{keyword}%", f"%{keyword}%"]
        sql += " ORDER BY id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def export_csv(self, path: str | Path, **filters) -> int:
        """导出成 CSV。用 utf-8-sig 编码，Excel 双击打开中文不乱码。"""
        rows = self.query(limit=None, **filters)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    # ---- 清理 ----

    def clear(self) -> None:
        """清空三张表，用于"重新开始一轮实验"。"""
        with self._lock:
            for table in ("pages", "pdf_links", "crawl_log"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.commit()
            self._pending = 0

    def close(self) -> None:
        if self._closed:
            return
        self.commit()
        self.conn.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
