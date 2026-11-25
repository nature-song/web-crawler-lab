"""主窗口：把四个面板拼起来，管状态机，从事件队列里取消息更新界面。

界面线程只做两件事：
  1. 收集用户输入，交给 CrawlEngine；
  2. 每 120ms 从 queue 里取一批事件，更新控件。
真正的抓取全在工作线程里，所以界面不会卡。
"""

import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from crawler.engine import CrawlEngine
from crawler.logger import setup_logger
from crawler.storage import Storage

from .widgets import LogPanel, ParamPanel, ResultTable, StatPanel

POLL_MS = 120
DB_PATH = "data/crawl.db"


class CrawlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("网络爬虫实验系统 · 选题一")
        self.geometry("1120x730")
        self.minsize(980, 640)

        self.events: queue.Queue = queue.Queue()
        self.storage = Storage(DB_PATH)
        self.engine: CrawlEngine | None = None
        self.state = "idle"
        self.started_at = 0.0

        self._build_layout()
        self._apply_state("idle")
        self.table.load(self.storage.query(limit=100))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_events)

    # ---- 布局 ----

    def _build_layout(self) -> None:
        self.params = ParamPanel(self)
        self.params.pack(fill="x")

        toolbar = ttk.Frame(self, padding=(12, 4, 12, 8))
        toolbar.pack(fill="x")
        self.start_btn = ttk.Button(toolbar, text="开始", command=self._on_start)
        self.pause_btn = ttk.Button(toolbar, text="暂停", command=self._on_pause)
        self.stop_btn = ttk.Button(toolbar, text="停止", command=self._on_stop)
        self.export_btn = ttk.Button(toolbar, text="导出 CSV", command=self._on_export)
        self.clear_btn = ttk.Button(toolbar, text="清空结果", command=self._on_clear)
        for button in (self.start_btn, self.pause_btn, self.stop_btn):
            button.pack(side="left", padx=(0, 8))
        self.export_btn.pack(side="left")
        self.clear_btn.pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, text="双击结果行可查看摘要").pack(side="right")

        self.stats_panel = StatPanel(self)
        self.stats_panel.pack(fill="x")

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=12, pady=(6, 6))

        log_frame = ttk.LabelFrame(paned, text="运行日志")
        table_frame = ttk.LabelFrame(paned, text="爬取结果")
        self.log_panel = LogPanel(log_frame)
        self.log_panel.pack(fill="both", expand=True, padx=4, pady=4)
        self.table = ResultTable(table_frame, on_double_click=self._show_detail)
        self.table.pack(fill="both", expand=True, padx=4, pady=4)
        paned.add(log_frame, weight=1)
        paned.add(table_frame, weight=2)

        status = ttk.Frame(self, padding=(12, 2, 12, 6))
        status.pack(fill="x")
        self.status_var = tk.StringVar(value="空闲")
        self.hint_var = tk.StringVar(value=f"数据库 {DB_PATH}")
        ttk.Label(status, textvariable=self.status_var, width=16).pack(side="left")
        ttk.Label(status, textvariable=self.hint_var).pack(side="left")

    # ---- 状态机 ----

    def _apply_state(self, state: str) -> None:
        self.state = state
        busy = state in ("running", "paused", "stopping")
        self.params.set_enabled(not busy)
        self._enable(self.start_btn, state in ("idle", "finished"))
        self._enable(self.pause_btn, state in ("running", "paused"))
        self._enable(self.stop_btn, state in ("running", "paused"))
        self._enable(self.export_btn, state in ("idle", "finished"))
        self._enable(self.clear_btn, state in ("idle", "finished"))
        self.pause_btn.configure(text="继续" if state == "paused" else "暂停")
        self.status_var.set(
            {"idle": "空闲", "running": "运行中", "paused": "已暂停",
             "stopping": "正在停止", "finished": "已结束"}[state]
        )

    @staticmethod
    def _enable(widget, enabled: bool) -> None:
        widget.state(["!disabled"] if enabled else ["disabled"])

    # ---- 按钮回调 ----

    def _on_start(self) -> None:
        if self.state not in ("idle", "finished"):
            return
        try:
            cfg = self.params.to_config()
        except ValueError as exc:
            messagebox.showwarning("参数不对", str(exc))
            return

        ok, message = cfg.validate()
        if not ok:
            messagebox.showwarning("参数不对", message)
            return

        setup_logger(cfg.log_path, event_queue=self.events, console=False)
        self.engine = CrawlEngine(cfg, storage=self.storage, event_queue=self.events)
        self.table.load(self.storage.query(limit=200))
        self.log_panel.append("INFO", f"开始爬取：{', '.join(cfg.seeds)}")
        self.started_at = time.monotonic()
        self._apply_state("running")
        self.engine.start()

    def _on_pause(self) -> None:
        if self.engine is None:
            return
        if self.state == "running":
            self.engine.pause()
            self._apply_state("paused")
        elif self.state == "paused":
            self.engine.resume()
            self._apply_state("running")

    def _on_stop(self) -> None:
        if self.engine is None:
            return
        self.engine.request_stop()
        self._apply_state("stopping")

    def _on_export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="导出结果",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="crawl_result.csv",
        )
        if not path:
            return
        try:
            saved = self.storage.export_csv(path)
        except OSError as exc:              # 文件被 Excel 占用之类
            messagebox.showerror("导出失败", f"写文件失败：{exc}")
            return
        self.log_panel.append("INFO", f"已导出 {saved} 条到 {path}")
        messagebox.showinfo("导出完成", f"已导出 {saved} 条记录到：\n{path}")

    def _on_clear(self) -> None:
        if self.state not in ("idle", "finished"):
            return
        if not messagebox.askyesno("清空结果", "确定清空数据库里的全部结果吗？此操作不可撤销。"):
            return
        self.storage.clear()
        self.table.clear()
        self.log_panel.append("INFO", "已清空结果")
        self.hint_var.set(f"数据库 {DB_PATH} · 共 0 条")

    def _on_close(self) -> None:
        if self.state in ("running", "paused"):
            if not messagebox.askyesno("还在爬取", "正在爬取，确定要退出吗？"):
                return
            self.engine.request_stop()
        if self.engine is not None and self.engine.is_running:
            self.engine.stop()
        self.storage.close()
        self.destroy()

    # ---- 事件桥 ----

    def _poll_events(self) -> None:
        handled = 0
        while handled < 200:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            handled += 1
            self._handle_event(event["type"], event["data"])

        if self.engine is not None and self.state in ("running", "paused", "stopping"):
            self.stats_panel.update(
                self.engine.snapshot(), self.engine.cfg.max_pages, self._elapsed()
            )
        self.after(POLL_MS, self._poll_events)

    def _handle_event(self, kind: str, data) -> None:
        if kind == "log":
            self.log_panel.append(data["level"], data["msg"], data.get("time", ""))
        elif kind == "page":
            self.table.add(data)
        elif kind == "state" and data == "finished":
            self._apply_state("finished")
            total = self.storage.count()
            self.table.load(self.storage.query(limit=200))
            self.hint_var.set(f"数据库 {DB_PATH} · 共 {total} 条")
        elif kind == "done":
            self.log_panel.append(
                "INFO",
                f"结束：成功 {data['fetched']}，失败 {data['failed']}，"
                f"PDF {data['pdf']}，去重 {data['dup']}",
            )

    def _elapsed(self) -> str:
        if not self.started_at:
            return "00:00"
        seconds = int(time.monotonic() - self.started_at)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _show_detail(self, row: dict) -> None:
        if not row:
            return
        window = tk.Toplevel(self)
        window.title("页面详情")
        window.geometry("760x440")
        text = tk.Text(window, wrap="word", padx=12, pady=10, font=("Microsoft YaHei UI", 10))
        text.pack(fill="both", expand=True)
        for key, label in (
            ("title", "标题"), ("authors", "作者"), ("publish_date", "发表时间"),
            ("keywords", "关键词"), ("site", "站点"), ("url", "URL"), ("abstract", "摘要"),
        ):
            text.insert("end", f"{label}：{row.get(key) or '—'}\n\n")
        text.configure(state="disabled")


def main() -> None:
    app = CrawlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
