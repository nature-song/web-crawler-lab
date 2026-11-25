"""启动 Web 界面。

    python run_web.py                 # 默认 http://127.0.0.1:5000，自动打开浏览器
    python run_web.py --port 5001     # 端口被占用时换一个
    python run_web.py --no-browser    # 不自动开浏览器
"""

import argparse

from web.server import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动网络爬虫工作台（Web 界面）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认只允许本机访问")
    parser.add_argument("--port", type=int, default=5000, help="端口，默认 5000")
    parser.add_argument("--debug", action="store_true", help="开发模式：改代码自动重载")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        host=args.host,
        port=args.port,
        debug=args.debug,
        open_browser=not args.no_browser,
    )
