"""环境自检脚本：全部通过说明环境可用。

用法：  .\\.venv\\Scripts\\python.exe verify_env.py
"""
import sqlite3
import sys
import tkinter

import bs4
import requests


def main() -> int:
    print(f"Python : {sys.version.split()[0]}  ({sys.executable})")
    print(f"Tk     : {tkinter.TkVersion}")
    print(f"SQLite : {sqlite3.sqlite_version}")
    print(f"requests: {requests.__version__} | bs4: {bs4.__version__}")
    try:
        import lxml  # noqa: F401
        print("lxml   : 已安装（bs4 可用 lxml 加速）")
    except ImportError:
        print("lxml   : 未安装（不影响，bs4 用 html.parser）")

    print("\n--- 网络连通性 ---")
    for url in ("https://www.python.org/", "https://www.baidu.com/"):
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "CourseCrawler/1.0"})
            title = bs4.BeautifulSoup(r.text, "html.parser").title
            print(f"OK  {r.status_code}  {url}  标题={title.get_text(strip=True)[:30] if title else ''}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {url}  {type(exc).__name__}: {exc}")

    print("\n环境检查结束。上面出现 OK 即可开始实验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
