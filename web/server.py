"""本地 Web 服务：浏览器界面 + 爬虫引擎。

一个进程干两件事：
  - Flask 处理 HTTP 请求（页面、API、SSE 事件流）；
  - CrawlEngine 在自己的线程里爬，事件写进 queue，SSE 再推给浏览器。

为什么用 SSE 而不是 WebSocket：日志是单向推送，SSE 更简单，浏览器自带重连。
"""

import json
import queue
import re
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from crawler.config import CrawlConfig
from crawler.engine import CrawlEngine
from crawler.logger import setup_logger
from crawler.storage import Storage

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "crawl.db"
LOG_PATH = PROJECT_ROOT / "logs" / "crawl.log"


class CrawlService:
    """把引擎、数据库、事件队列包在一起，供 HTTP 层调用。"""

    def __init__(self, db_path: Path = DB_PATH, log_path: Path = LOG_PATH):
        self.storage = Storage(db_path)
        self.log_path = log_path
        self.events: queue.Queue = queue.Queue()
        self.engine: CrawlEngine | None = None
        self._lock = threading.Lock()

    def start(self, cfg: CrawlConfig) -> tuple[bool, str]:
        with self._lock:
            if self.engine is not None and self.engine.is_running:
                return False, "已经有一个任务在跑了，先停止或等它结束"
            setup_logger(self.log_path, event_queue=self.events, console=False)
            self.engine = CrawlEngine(cfg, storage=self.storage, event_queue=self.events)
            self.engine.start()
            return True, ""

    def stop(self) -> None:
        if self.engine is not None:
            self.engine.request_stop()

    def pause(self) -> None:
        if self.engine is not None:
            self.engine.pause()

    def resume(self) -> None:
        if self.engine is not None:
            self.engine.resume()

    def snapshot(self) -> dict:
        if self.engine is None:
            return {}
        return self.engine.snapshot()

    def state(self) -> str:
        if self.engine is None:
            return "idle"
        return "running" if self.engine.is_running else "finished"


def _config_from_json(data: dict) -> CrawlConfig:
    """把前端传来的 JSON 转成 CrawlConfig。类型不对会抛 ValueError，由调用方转成 400。"""
    seeds = data.get("seeds") or []
    if isinstance(seeds, str):
        seeds = [item for item in re.split(r"[\s,，]+", seeds) if item]

    return CrawlConfig(
        seeds=[str(seed) for seed in seeds],
        strategy=str(data.get("strategy", "bfs")),
        max_depth=int(data.get("max_depth", 3)),
        max_pages=int(data.get("max_pages", 100)),
        workers=int(data.get("workers", 4)),
        interval=float(data.get("interval", 1.0)),
        same_domain=bool(data.get("same_domain", True)),
        respect_robots=bool(data.get("respect_robots", True)),
    )


def create_app(service: CrawlService | None = None) -> Flask:
    """应用工厂。测试时可以传入假 service，避免真的去爬网。"""
    service = service or CrawlService()
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "state": service.state()})

    @app.post("/api/crawl/start")
    def start():
        data = request.get_json(silent=True) or {}
        try:
            cfg = _config_from_json(data)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": f"参数格式不对：{exc}"}), 400

        ok, message = cfg.validate()
        if not ok:
            return jsonify({"error": message}), 400

        started, message = service.start(cfg)
        if not started:
            return jsonify({"error": message}), 409
        return jsonify({"ok": True})

    @app.post("/api/crawl/stop")
    def stop():
        service.stop()
        return jsonify({"ok": True})

    @app.post("/api/crawl/pause")
    def pause():
        service.pause()
        return jsonify({"ok": True})

    @app.post("/api/crawl/resume")
    def resume():
        service.resume()
        return jsonify({"ok": True})

    @app.get("/api/stats")
    def stats():
        return jsonify(service.snapshot())

    @app.get("/api/results")
    def results():
        limit = request.args.get("limit", default=200, type=int)
        site = request.args.get("site", default="")
        keyword = request.args.get("keyword", default="")
        return jsonify(service.storage.query(limit=limit, site=site, keyword=keyword))

    @app.get("/api/export.csv")
    def export_csv():
        import csv
        import io

        buffer = io.StringIO()
        rows = service.storage.query(limit=None)
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        payload = "\ufeff" + buffer.getvalue()      # BOM：Excel 打开不乱码
        return Response(
            payload,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=crawl_result.csv"},
        )

    @app.post("/api/clear")
    def clear():
        service.storage.clear()
        return jsonify({"ok": True})

    @app.get("/api/events")
    def events():
        """SSE：把引擎产生的事件一条条推给浏览器。"""

        def stream():
            while True:
                try:
                    event = service.events.get(timeout=15)
                except queue.Empty:
                    yield ": keepalive\n\n"         # 防止代理/浏览器超时断开
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return Response(
            stream(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def main(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app = create_app()
    print(f"界面地址： http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
