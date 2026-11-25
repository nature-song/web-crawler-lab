"""网络爬虫核心包（不含界面）。

依赖方向是单向的：本包不知道界面的存在，所以可以脱离 GUI 单独跑、单独测。

    models.py     数据结构：Task / Page / FetchResult / Stats
    config.py     参数与校验
    url_utils.py  URL 规范化与过滤
    frontier.py   请求队列（BFS / DFS / 最佳优先）
    fetcher.py    HTTP 抓取（不抛异常，返回 FetchResult）
    robots.py     robots.txt 解析与缓存
    ratelimit.py  按域名限速
    parser.py     六字段抽取（待写）
    storage.py    SQLite 读写（待写）
    logger.py     日志配置（待写）
    engine.py     调度主循环（待写）
"""
