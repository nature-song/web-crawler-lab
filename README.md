# 网络爬虫实验系统

《网络系统实践》（950012Z11）选题一：**带图形界面的教学用网络爬虫**。
按策略爬网页、遵守 robots.txt、按域名限速、抽取标题/作者/摘要/关键词/时间/URL，存进 SQLite，最后在界面上看结果并导出。

技术栈：Python 3.14 + Tkinter + requests + BeautifulSoup + SQLite。**不使用 Scrapy**，调度、去重、限速全部手写（课程要求）。

---

## 一、现在做到哪了

| 模块 | 文件 | 作用 | 状态 | 测试 |
|---|---|---|---|---|
| 参数配置 | `crawler/config.py` | 所有参数集中定义 + 合法性校验 | ✅ | 9 |
| URL 工具 | `crawler/url_utils.py` | 规范化、同域判断、后缀过滤 | ✅ | 16 |
| 请求队列 | `crawler/frontier.py` | BFS / DFS / 最佳优先 + 去重 | ✅ | 7 |
| HTTP 抓取 | `crawler/fetcher.py` | 超时、重试、编码识别、类型判定 | ✅ | 10 |
| robots | `crawler/robots.py` | 抓取、解析、缓存（含 `*` `$` 通配符） | ✅ | 9 |
| 限速 | `crawler/ratelimit.py` | 按域名控制请求间隔 | ✅ | 3 |
| 信息抽取 | `crawler/parser.py` | 六字段抽取 + 抽新链接 | ✅ | 17 |
| 存储 | `crawler/storage.py` | SQLite 建表、写入、查询、导出 | ✅ | 10 |
| 日志 | `crawler/logger.py` | 文件 + 界面事件双通道 | ✅ | 2 |
| 调度引擎 | `crawler/engine.py` | 取任务→抓取→解析→入库→入队 | ✅ | 9 |
| 命令行 | `crawler/cli.py` | 不启动界面的入口 | ✅ | — |
| 图形界面 | `ui/app.py` | 参数面板、启停、日志、表格 | ⬜ | — |

**当前 92 个单元测试全部通过。**

## 二、目录结构

```
.
├─ run.py                   # 程序入口（界面做好后才有内容）
├─ requirements.txt         # 需要安装的第三方包清单
├─ crawler/                 # 爬虫核心（不含界面，可单独跑）
│  ├─ config.py             # 参数定义与校验
│  ├─ models.py             # 共享数据结构：Task / Page / FetchResult / Stats
│  ├─ url_utils.py          # URL 规范化、过滤
│  ├─ frontier.py           # 请求队列与三种策略
│  ├─ fetcher.py            # HTTP 抓取
│  ├─ robots.py             # robots.txt 解析与缓存
│  ├─ ratelimit.py          # 按域名限速
│  ├─ parser.py             # 六字段抽取 + 链接提取
│  ├─ storage.py            # SQLite 存取与 CSV 导出
│  ├─ logger.py             # 日志（文件 + 界面事件）
│  ├─ engine.py             # 调度主循环
│  └─ cli.py                # 命令行入口
├─ ui/                      # 图形界面
├─ tests/                   # 单元测试，test_*.py 会被自动收集
├─ docs/                    # 设计文档、命令手册
├─ data/                    # crawl.db（运行后生成，不进 git）
└─ logs/                    # 运行日志（不进 git）
```

## 三、快速开始

```powershell
# 1. 进项目目录
cd D:\userfiles\desktop\网络系统实践

# 2. 激活虚拟环境（命令行前面出现 (.venv) 就成功了）
.\.venv\Scripts\Activate.ps1

# 3. 装依赖（已经装过就不用重复执行）
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 跑测试，确认代码是好的
python -m pytest -q
```

每条命令在干嘛：

| 命令 | 作用 |
|---|---|
| `cd 路径` | 切换当前工作目录，后面的命令都在这个目录下执行 |
| `Activate.ps1` | 让这个终端里的 `python` 指向 `.venv` 里的解释器 |
| `pip install -r requirements.txt` | 按清单把 requests / bs4 / lxml / pytest 装上 |
| `python -m pytest -q` | 运行 `tests/` 里所有测试，`-q` 表示少打印点 |

> 不想激活也行：把 `python` 换成 `.\.venv\Scripts\python.exe` 即可，效果一样。

## 四、怎么调试

**① 跑测试（最常用）**

```powershell
python -m pytest -q                          # 全部，只看结果
python -m pytest tests/test_robots.py -v     # 只跑 robots 的测试，-v 显示每个用例名
python -m pytest tests/test_robots.py::test_wildcard_and_anchor -v   # 只跑一个用例
```

测试挂了会直接告诉你哪个断言不成立、期望值和实际值各是什么，按提示改代码即可。

**② 交互式试函数**

```powershell
python -i -c "from crawler.url_utils import normalize_url; print(normalize_url('HTTP://A.com:80/x/../y'))"
```

`-i` 表示执行完不退出，停在 Python 提示符，可以接着敲别的表达式。

**③ 打断点**

VSCode 里在行号左边点一下出现红点 → 按 `F5` → 程序停在那行，鼠标悬停看变量值，`F10` 单步。

**④ 看日志**

运行后会写 `logs/crawl_YYYYMMDD.log`，每个失败请求都带 URL 和错误原因，排查"为什么这个页面没抓到"就靠它。

## 五、代码约定

1. **分层**：`ui` 可以 import `crawler`，`crawler` 绝不 import `ui`。所以爬虫核心可以脱离界面单独测。
2. **数据结构集中在 `models.py`**，避免模块之间互相 import 形成环。
3. **网络层不抛异常**：`Fetcher.fetch()` 一律返回 `FetchResult`，`kind="error"` 表示失败。调用方不用写 try/except。
4. **可注入依赖**：`Fetcher(session=...)`、`RobotsCache(fetch_text=...)` 都能传假的，测试才不用连网。
5. **注释写"为什么"**，不写"是什么"；能一眼看懂的地方不加注释。
6. **一个文件一件事**，单个函数尽量不超过 40 行。

## 六、文档索引

| 文档 | 什么时候看 |
|---|---|
| [实验规划](实验规划-网络爬虫.md) | 想知道五周怎么排、算法怎么讲、答辩会问什么 |
| [需求分析报告](docs/01-需求分析报告.md) | 想知道每条需求从哪来、怎么验收 |
| [体系设计报告](docs/02-体系设计报告.md) | 想知道模块怎么划分、数据库怎么设计 |
| [命令手册](docs/命令手册.md) | 终端命令看不懂的时候查 |
| [AGENTS.md](AGENTS.md) | 换 AI 或换人接手时先看这个 |

## 七、下一步

1. `ui/`：Tkinter 界面（参数面板 / 启停 / 日志 / 结果表格）
2. 本地测试站点 + 端到端演示
3. 真实站点试跑与实验数据

## 八、合规说明

只抓公开页面；遵守 robots.txt；默认 1 请求/秒/域；User-Agent 带项目标识；不采集个人信息；抓取结果仅用于课程实验。
