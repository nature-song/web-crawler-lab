# AGENTS.md

给接手这个项目的 AI 或同学看的说明。读完这个文件再动代码。

## 项目是什么

《网络系统实践》课程作业，选题一：带图形界面的网络爬虫。单人开发，共 5 周，目前在第 2 周。

**硬性要求（来自教学大纲，不可删减）**：三种爬取策略至少一种、robots 遵守、URL 去重、PDF 链接处理、六字段抽取、限速、日志、图形界面启停与状态展示。

## 技术约束

- Python 3.14，Windows，虚拟环境在 `.venv`（不要用系统 Python 3.9）
- GUI 用 **Tkinter**，不用 PySide6/Qt
- **不用 Scrapy 或任何爬虫框架**——课程考的就是手写队列/去重/限速
- 依赖只有 requests、beautifulsoup4、lxml、pytest，新增依赖前先说明理由

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
ui/          Tkinter 界面，只负责显示与收集输入
tests/       pytest，81 个用例
```

**依赖方向**：`ui → crawler`，反向禁止。`crawler` 内部所有模块只能 import `models / config / url_utils`。

## 常用命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # 跑测试，必须全绿才算完成
.\.venv\Scripts\python.exe -m pytest tests/test_fetcher.py -v
git add -A; git commit -m "feat: ..."; git push
```

## 写代码的约定

1. 注释写中文，解释**为什么**这么做，不写"本函数用于…"这种废话。
2. 函数要短，超过 40 行就考虑拆。
3. 新增模块先定义接口（函数签名 + 返回类型），再写实现。
4. 需要外部依赖的地方（网络、时间、文件）都要能注入假实现，否则测试没法离线跑。
5. 提交信息用 `feat: / fix: / docs: / test: / chore:` 开头。

## 当前进度与下一步

已完成：config、url_utils、frontier、fetcher、robots、ratelimit、parser、storage（含 81 个测试）。
下一步：`logger.py` → `engine.py`（命令行能跑）→ `ui/`。

## 不要做的事

- 不要把网络请求直接写进界面代码
- 不要在 `crawler` 里 import `tkinter`
- 不要为了"看起来完整"而编造实验数据或访谈记录（报告里有【】占位待本人填写）
- 不要删 `requirements.txt`
- 不要用 `git push --force`
