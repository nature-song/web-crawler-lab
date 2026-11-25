# AGENTS.md

给接手这个项目的 AI 或同学看的说明。读完这个文件再动代码。

## 项目是什么

《网络系统实践》课程作业，选题一：带图形界面的网络爬虫。单人开发。**v1 已打通完整闭环，正在做 v2（见 docs/03-项目现状与差距分析.md）**。

**硬性要求（来自教学大纲，不可删减）**：三种爬取策略至少一种、robots 遵守、URL 去重、PDF 链接处理、六字段抽取、限速、日志、图形界面启停与状态展示。

## 技术约束

- Python 3.14，Windows，虚拟环境在 `.venv`（不要用系统 Python 3.9）
- 界面：**Web（Flask + 原生 JS）为主入口**，Tkinter 桌面版保留为备用；不用 React/Vue（要 node 构建）
- **不用 Scrapy 或任何爬虫框架**——课程考的就是手写队列/去重/限速
- 依赖只有 requests、beautifulsoup4、lxml、pytest、flask，新增依赖前先说明理由

## 代码结构

```
crawler/     核心引擎，纯 Python，不含任何界面代码
  models.py    共享数据结构（Task/Page/FetchResult/Stats），谁都可以依赖它，它不依赖别人
  config.py    参数集中定义 + validate()
  url_utils.py URL 规范化与过滤
  frontier.py  BFS/DFS/best 队列 + 去重
  fetcher.py   HTTP（不抛异常，返回 FetchResult）
  robots.py    robots.txt 解析（自研，支持 * 和 $）
  ratelimit.py 按域名限速
  parser.py    六字段抽取 + 链接提取
  storage.py   SQLite 存取与 CSV 导出
  logger.py    日志（文件 + 事件队列）
  engine.py    调度主循环（线程池 + 统计）
  cli.py       命令行入口：python -m crawler.cli
web/         Web 界面（主入口）
  server.py   Flask 路由 + SSE 事件流 + CrawlService
  static/     index.html / app.js / style.css（无构建链）
ui/          Tkinter 桌面版，只负责显示与收集输入
  app.py       主窗口：布局 + 状态机 + 事件桥（queue + after）
  widgets.py   参数 / 统计 / 日志 / 结果表 四个面板
tests/       pytest，106 个用例
```

**依赖方向**：`ui → crawler`，反向禁止。`crawler` 内部所有模块只能 import `models / config / url_utils`。

## 常用命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # 跑测试，必须全绿才算完成
.\.venv\Scripts\python.exe -m pytest tests/test_fetcher.py -v
.\.venv\Scripts\python.exe -m ruff check crawler ui tests run.py   # 静态检查必须零错误
git add -A; git commit -m "feat: ..."; git push
```

## 写代码的约定

1. 注释写中文，解释**为什么**这么做，不写"本函数用于…"这种废话。
2. 函数要短，超过 40 行就考虑拆。
3. 新增模块先定义接口（函数签名 + 返回类型），再写实现。
4. 需要外部依赖的地方（网络、时间、文件）都要能注入假实现，否则测试没法离线跑。
5. 提交信息用 `feat: / fix: / docs: / test: / chore:` 开头。

## 当前进度与下一步

已完成：核心引擎 + Tkinter 桌面版 + Flask Web 版（106 个测试、ruff 零告警）。
三个入口：`python run_web.py`（浏览器）/ `python run.py`（桌面）/ `python -m crawler.cli`（命令行）。
下一步：按 docs/04 产品设计的 M2 → M5 推进（数据检索 → 看板与任务历史 → 增量采集 → 打磨）。
质量基线：pytest 全绿 + `python -m ruff check crawler ui tests run.py` 零错误，缺一不可。

## 不要做的事

- 不要把网络请求直接写进界面代码
- 不要在 `crawler` 里 import `tkinter`
- 不要为了"看起来完整"而编造实验数据或访谈记录（报告里有【】占位待本人填写）
- 不要删 `requirements.txt`
- 不要用 `git push --force`
