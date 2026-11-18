# 网络爬虫实验系统

> 《网络系统实践》（950012Z11）课程实践 · **选题一：网络爬虫的设计与实现**
> 一个带图形界面的教学用网络爬虫：请求队列调度、三种爬取策略、robots 协议遵守、按域名限速、结构化信息抽取、SQLite 持久化。

---

## 一、目标与范围

严格对照教学大纲"五、实践教学内容 → 实践选题（1）"的四条要求设计：

| # | 大纲要求 | 本项目的实现方案 | 状态 |
|---|---|---|---|
| 1 | 基于请求队列的广度 / 深度 / 最佳优先策略（至少实现一种以上） | `Frontier` 抽象：`deque` 实现 FIFO(BFS)/LIFO(DFS)，`heapq` 实现优先级队列；界面可实时切换 | 待实现 |
| 1 | Robots 协议解析与遵守 | 自抓 `robots.txt`（带 UA/超时）→ `RobotFileParser.parse()` → 按 host 缓存 + TTL，并补上标准库缺失的 `*`/`$` 通配符匹配 | 待实现 |
| 1 | URL 去重、PDF 链接处理 | 8 条规则的 URL 规范化 + 哈希集合去重 + 数据库 `UNIQUE` 双保险；PDF 三重判定后单独记账，不参与 HTML 解析 | 待实现 |
| 2 | 提取标题、作者、摘要、关键词、发表时间、URL 并保存 | "元数据优先（citation_*/DC.*/og:*）+ DOM 兜底 + 正则日期"三级抽取链，写入 SQLite，支持导出 CSV/Excel | 待实现 |
| 3 | 爬取速率控制（请求间隔） | 按域名的 `DomainRateLimiter`（锁内预约时间片、锁外睡眠）+ 线程池并发上限 | 待实现 |
| 3 | 监控爬取状态、记录爬取日志 | 界面实时统计（已抓/待抓/失败/去重/robots 拦截/PDF）+ 滚动日志文件 | 待实现 |
| 3 | 异常处理（网络异常、解析失败） | 超时/连接失败/429/403/5xx 分类处理 + 指数退避重试 + 单页解析异常兜底 | 待实现 |
| 4 | 图形界面友好、可控开始结束、显示状态与结果 | Tkinter + ttk：参数面板、开始/暂停/停止、进度条、实时日志、结果表格、导出 | 待实现 |

> 状态图例：`待实现` / `进行中` / `已完成`。全部完成后本表即为验收清单。

## 二、技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.14 | 爬虫生态成熟；课程允许；开发效率高 |
| GUI | Tkinter + ttk | 标准库自带，零安装、零版本冲突，现场演示最稳 |
| HTTP | `requests` | 会话复用、超时/重试控制清晰 |
| 解析 | `beautifulsoup4`（`lxml` 加速） | 对残缺 HTML 容错好 |
| 存储 | `sqlite3` | 标准库自带，单文件随项目拷走 |
| 并发 | `threading` + `ThreadPoolExecutor` | 爬虫是 IO 密集型，GIL 不是瓶颈 |
| 测试 | `pytest` | 单元测试 + 集成测试 |

**不使用 Scrapy**：本实验考核重点是队列、去重、限速、解析这些"轮子"本身的实现，框架会把这些变成配置项，既不利于学习，也无法在报告中阐述算法设计。

## 三、快速开始

环境要求：Windows + Python 3.10 以上（推荐 3.14）。

```powershell
# 1. 创建并激活虚拟环境
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖（国内可用清华源）
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 环境自检（应输出 Python 版本、Tk 版本与两条 OK）
python verify_env.py

# 4. 启动（开发完成后）
python run.py
```

## 四、目录结构

```
.
├─ run.py                   # 唯一入口
├─ verify_env.py            # 环境自检脚本
├─ requirements.txt
├─ crawler/                 # 爬虫核心包
│  ├─ url_utils.py          # URL 规范化、过滤
│  ├─ frontier.py           # 队列 + 去重 + 三种策略
│  ├─ robots.py             # robots.txt 解析与缓存
│  ├─ ratelimit.py          # 按域限速
│  ├─ fetcher.py            # HTTP 请求与重试
│  ├─ parser.py             # 六字段抽取
│  ├─ storage.py            # SQLite
│  ├─ logger.py             # 日志
│  └─ engine.py             # 调度主循环
├─ ui/                      # Tkinter 界面
├─ tests/                   # pytest 用例 + 本地测试站点
├─ data/                    # crawl.db（不入库）
├─ logs/                    # 运行日志（不入库）
└─ 实验规划-网络爬虫.md      # 五周实施规划、算法详解、报告模板
```

## 五、开发路线

- [ ] **W1** 命令行最小爬虫：HTTP 抓取 → 抽链接 → BFS 队列 → 去重 → 深度限制
- [ ] **W1** robots.txt 解析与遵守、按域限速、日志与异常分类
- [ ] **W2** 六字段抽取（元数据优先 + DOM 兜底）、SQLite 落库、CSV 导出
- [ ] **W2** DFS 与最佳优先策略、线程池并发
- [ ] **W3** GUI：布局、事件桥（`queue` + `after`）、状态机、实时日志与结果表格
- [ ] **W3** 稳定性专项：连启停 10 次、长跑 30 分钟、爬取中关窗
- [ ] **W4** 本地测试站点 + 20 条功能测试用例
- [ ] **W4** 三策略对比实验、限速实验、图表
- [ ] **W5** 实践报告与答辩材料

详细到"每天做什么、完成标志是什么"见 [实验规划](./实验规划-网络爬虫.md)。

## 六、合规声明

本项目仅用于课程实验，遵循以下原则：

- 遵守目标站点 `robots.txt`，被禁止的路径一律不抓；
- 按域名限速（默认 1 请求/秒/域），并发不超过 4，避免对目标服务器造成压力；
- 请求头携带可识别的 User-Agent，不伪装成浏览器；
- 只抓取公开页面，不登录、不绕过验证码或付费墙，不采集个人信息；
- 抓取数据仅用于课程分析，实验结束后清理原始网页快照，报告引用标注来源。

## 七、参考

- RFC 9309 — Robots Exclusion Protocol
- Python 官方文档：`urllib.robotparser`、`sqlite3`、`tkinter`、`concurrent.futures`
- requests / BeautifulSoup 官方文档
- 詹姆斯·F. 库罗斯《计算机网络：自顶向下方法》（原书第 8 版）第 2 章
