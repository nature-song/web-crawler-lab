"""命令行入口：不启动界面，直接爬一批看效果。

示例：
    python -m crawler.cli --seed https://www.python.org/ --max 5 --interval 0.5
    python -m crawler.cli --seed http://127.0.0.1:8000/ --max 30 --csv data/out.csv

界面做好以后，这个入口仍然有用：调试引擎时不用等界面加载。
"""

import argparse
import sys

from .config import CrawlConfig
from .engine import CrawlEngine
from .logger import setup_logger
from .storage import Storage


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="网络爬虫实验系统 · 命令行版")
    parser.add_argument("--seed", action="append", required=True, help="种子 URL，可写多次")
    parser.add_argument("--strategy", default="bfs", choices=("bfs", "dfs", "best"))
    parser.add_argument("--max", type=int, default=50, dest="max_pages", help="最多抓多少页")
    parser.add_argument("--depth", type=int, default=3, dest="max_depth", help="最大深度")
    parser.add_argument("--interval", type=float, default=1.0, help="同域名请求间隔（秒）")
    parser.add_argument("--workers", type=int, default=4, help="并发线程数")
    parser.add_argument("--db", default="data/crawl.db", help="数据库路径")
    parser.add_argument("--log", default="logs/crawl.log", help="日志路径")
    parser.add_argument("--csv", default="", help="结束后导出 CSV 到哪里")
    parser.add_argument("--no-robots", action="store_true", help="临时关闭 robots 检查（仅调试用）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = CrawlConfig(
        seeds=args.seed,
        strategy=args.strategy,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        interval=args.interval,
        workers=args.workers,
        db_path=args.db,
        log_path=args.log,
        respect_robots=not args.no_robots,
    )

    ok, message = cfg.validate()
    if not ok:
        print(f"参数不合法：{message}", file=sys.stderr)
        return 2

    setup_logger(cfg.log_path, console=True)
    with Storage(cfg.db_path) as storage:
        engine = CrawlEngine(cfg, storage=storage)
        engine.run()
        print(f"\n完成：{cfg.db_path} 共 {storage.count()} 条，"
              f"PDF 链接 {storage.count_pdf()} 条")
        if args.csv:
            saved = storage.export_csv(args.csv)
            print(f"已导出 {saved} 条到 {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
