"""界面里的四个面板：参数、统计、日志、结果表。

拆出来的原因：主窗口只负责"把它们拼起来 + 管状态"，不掺和控件细节。
每个面板自己建控件、暴露一个简单方法，外面不需要知道里面有几个 Label。
"""

import re
import tkinter as tk
from tkinter import ttk

from crawler.config import CrawlConfig

# 界面显示中文，内部用英文枚举值
STRATEGY_LABELS = {"广度优先": "bfs", "深度优先": "dfs", "最佳优先": "best"}


class ParamPanel(ttk.Frame):
    """种子地址 + 策略 + 四个数值参数 + 三个开关。"""

    def __init__(self, master):
        super().__init__(master, padding=(12, 10, 12, 4))
        self.seed_var = tk.StringVar(value="https://www.python.org/")
        self.strategy_var = tk.StringVar(value="广度优先")
        self.depth_var = tk.IntVar(value=3)
        self.pages_var = tk.IntVar(value=100)
        self.workers_var = tk.IntVar(value=4)
        self.interval_var = tk.DoubleVar(value=1.0)
        self.same_domain_var = tk.BooleanVar(value=True)
        self.robots_var = tk.BooleanVar(value=True)
        self._inputs: list = []
        self._build()

    def _build(self) -> None:
        first = ttk.Frame(self)
        first.pack(fill="x")
        ttk.Label(first, text="种子 URL").pack(side="left")
        seed_entry = ttk.Entry(first, textvariable=self.seed_var, width=58)
        seed_entry.pack(side="left", padx=(8, 8))
        ttk.Label(first, text="多个用空格分隔").pack(side="left")
        self._inputs.append(seed_entry)

        second = ttk.Frame(self)
        second.pack(fill="x", pady=(8, 0))
        ttk.Label(second, text="策略").pack(side="left")
        strategy = ttk.Combobox(
            second, textvariable=self.strategy_var, state="readonly",
            values=list(STRATEGY_LABELS), width=8,
        )
        strategy.pack(side="left", padx=(4, 14))
        self._inputs.append(strategy)

        self._add_spin(second, "深度", self.depth_var, 0, 10, 1, 4)
        self._add_spin(second, "页数", self.pages_var, 1, 10000, 50, 6)
        self._add_spin(second, "并发", self.workers_var, 1, 8, 1, 3)
        self._add_spin(second, "间隔(秒)", self.interval_var, 0.1, 10, 0.1, 5)

        third = ttk.Frame(self)
        third.pack(fill="x", pady=(8, 0))
        for text, var in (
            ("仅本站", self.same_domain_var),
            ("遵守 robots", self.robots_var),
        ):
            check = ttk.Checkbutton(third, text=text, variable=var)
            check.pack(side="left", padx=(0, 16))
            self._inputs.append(check)

    def _add_spin(self, parent, text, var, low, high, step, width) -> None:
        ttk.Label(parent, text=text).pack(side="left")
        spin = ttk.Spinbox(
            parent, textvariable=var, from_=low, to=high, increment=step,
            width=width, justify="center",
        )
        spin.pack(side="left", padx=(4, 14))
        self._inputs.append(spin)

    def to_config(self) -> CrawlConfig:
        """把界面上的值收成一个 CrawlConfig。值不合法时抛 ValueError。"""
        seeds = [item for item in re.split(r"[\s,，]+", self.seed_var.get().strip()) if item]
        if not seeds:
            raise ValueError("请至少填一个种子 URL")

        return CrawlConfig(
            seeds=seeds,
            strategy=STRATEGY_LABELS[self.strategy_var.get()],
            max_depth=self._int(self.depth_var, "深度"),
            max_pages=self._int(self.pages_var, "页数"),
            workers=self._int(self.workers_var, "并发"),
            interval=self._float(self.interval_var, "间隔"),
            same_domain=self.same_domain_var.get(),
            respect_robots=self.robots_var.get(),
        )

    @staticmethod
    def _int(var, name: str) -> int:
        try:
            return int(var.get())
        except (tk.TclError, ValueError):
            raise ValueError(f"{name}必须填整数") from None

    @staticmethod
    def _float(var, name: str) -> float:
        try:
            return float(var.get())
        except (tk.TclError, ValueError):
            raise ValueError(f"{name}必须填数字") from None

    def set_enabled(self, enabled: bool) -> None:
        """运行中锁住参数，避免一边跑一边改。"""
        for widget in self._inputs:
            widget.state(["!disabled"] if enabled else ["disabled"])


class StatPanel(ttk.Frame):
    """进度条 + 一排计数。分两行放，窗口窄了也不会被挤出去。"""

    COUNTERS = (
        ("fetched", "已抓"), ("queued", "待抓"), ("failed", "失败"),
        ("dup", "去重"), ("blocked", "robots"), ("pdf", "PDF"),
    )

    def __init__(self, master):
        super().__init__(master, padding=(12, 4))

        first = ttk.Frame(self)
        first.pack(fill="x")
        self.progress = ttk.Progressbar(first, mode="determinate", length=420)
        self.progress.pack(side="left", padx=(0, 10))
        self.progress_text = tk.StringVar(value="0 / 0")
        ttk.Label(first, textvariable=self.progress_text, width=14).pack(side="left")
        self.elapsed_text = tk.StringVar(value="00:00")
        ttk.Label(first, textvariable=self.elapsed_text).pack(side="right")

        second = ttk.Frame(self)
        second.pack(fill="x", pady=(6, 0))
        self.counters: dict[str, tk.StringVar] = {}
        for key, label in self.COUNTERS:
            var = tk.StringVar(value="0")
            self.counters[key] = var
            ttk.Label(second, text=f"{label}:").pack(side="left")
            ttk.Label(second, textvariable=var, width=5).pack(side="left", padx=(2, 14))

    def update(self, stats: dict, limit: int, elapsed: str) -> None:
        fetched = int(stats.get("fetched", 0))
        self.progress.configure(maximum=max(limit, 1), value=min(fetched, limit))
        self.progress_text.set(f"{fetched} / {limit}")
        for key, var in self.counters.items():
            var.set(str(stats.get(key, 0)))
        self.elapsed_text.set(elapsed)


class LogPanel(ttk.Frame):
    """滚动日志。只留最近 2000 行，跑久了也不会把界面拖死。"""

    MAX_LINES = 2000

    def __init__(self, master):
        super().__init__(master)
        self.text = tk.Text(self, width=40, height=12, wrap="none", state="disabled",
                            font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.text.tag_configure("WARN", foreground="#b26a00")
        self.text.tag_configure("ERROR", foreground="#b00020")

    def append(self, level: str, message: str, timestamp: str = "") -> None:
        self.text.configure(state="normal")
        line = f"{timestamp} {message}" if timestamp else message
        self.text.insert("end", line + "\n", level if level in ("WARN", "ERROR") else "")
        if int(self.text.index("end-1c").split(".")[0]) > self.MAX_LINES:
            self.text.delete("1.0", "500.0")
        self.text.see("end")
        self.text.configure(state="disabled")


class ResultTable(ttk.Frame):
    """结果表格。列宽按窗口伸缩，太窄时出现横向滚动条。"""

    COLUMNS = (
        ("title", "标题", 190),
        ("authors", "作者", 70),
        ("publish_date", "时间", 90),
        ("site", "站点", 100),
        ("url", "URL", 200),
    )

    def __init__(self, master, on_double_click=None):
        super().__init__(master)
        self._on_double_click = on_double_click
        self._rows: dict[str, dict] = {}

        self.tree = ttk.Treeview(
            self, columns=[name for name, _, _ in self.COLUMNS],
            show="headings", height=14,
        )
        for name, title, width in self.COLUMNS:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=60, anchor="w", stretch=True)

        vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._handle_double_click)

    def add(self, row: dict) -> None:
        values = [str(row.get(name, ""))[:80] for name, _, _ in self.COLUMNS]
        item = self.tree.insert("", "end", values=values)
        self._rows[item] = row

    def load(self, rows: list[dict]) -> None:
        self.clear()
        for row in rows:
            self.add(row)

    def clear(self) -> None:
        self._rows.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _handle_double_click(self, _event) -> None:
        item = self.tree.focus()
        if not item or self._on_double_click is None:
            return
        row = self._rows.get(item)
        if row:
            self._on_double_click(row)
