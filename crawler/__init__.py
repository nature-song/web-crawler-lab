"""网络爬虫实验系统 —— 核心包。

模块规划（按开发顺序）：
    url_utils.py  URL 规范化、同域判断、后缀过滤
    frontier.py   请求队列 + 去重 + BFS / DFS / 最佳优先
    robots.py     robots.txt 抓取、解析、缓存（含通配符匹配）
    ratelimit.py  按域名限速
    fetcher.py    HTTP 请求、重试、编码识别、PDF/非 HTML 判定
    parser.py     HTML → 标题/作者/摘要/关键词/时间/URL
    storage.py    SQLite 建表、写入、查询、导出
    logger.py     日志（文件 + GUI 事件队列）
    engine.py     调度主循环（核心）
"""
