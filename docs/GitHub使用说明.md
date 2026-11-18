# Git 与 GitHub 使用说明

> 目标：本地开发 + GitHub 备份/展示，每一步都可回退，答辩时能拿出完整的提交历史（这也是"课程目标 7：进度管理"的证据）。

## 一、一句话结论

**本地写代码 → `commit` 记录里程碑 → `push` 到 GitHub 备份 → 用 Issues 记进度。**
不需要在网页上写代码，也不需要一开始就配 SSH。

## 二、推荐路线：网页建库 + HTTPS 推送

### 第 1 步：在 GitHub 上建一个空仓库

1. 打开 <https://github.com/new>
2. Repository name 填 `web-crawler-lab`（名字随意）
3. 可见性选 **Private**（建议答辩结束再改 Public，避免同学抄、也避免版权问题）
4. **不要**勾选 "Add a README file"、".gitignore"、"license"——本地已经有了，勾了会产生冲突
5. 点 Create repository

### 第 2 步：把本地仓库连上去（只做一次）

在项目根目录执行（把 `<你的用户名>` 换成你的 GitHub 用户名）：

```powershell
git remote add origin https://github.com/<你的用户名>/web-crawler-lab.git
git push -u origin main
```

第一次推送会弹出 **Git Credential Manager** 窗口：

- 选 **Sign in with your browser** → 浏览器里登录 GitHub → 授权 → 回到窗口提示成功；
- 凭据会存进 Windows 凭据管理器，以后 `git push` 不再询问。

> 本机已确认 `credential.helper=manager`（系统级配置），所以弹窗逻辑是通的。若弹窗被拦，可在 PowerShell 里手动执行一次：
> `& 'D:\Git\mingw64\bin\git-credential-manager.exe' configure`

### 第 3 步：以后每次提交

```powershell
git status                    # 看改了什么
git add -A                    # 全部暂存（或 git add crawler/frontier.py）
git commit -m "feat: 实现 BFS/DFS/最佳优先三种队列策略"
git push                      # 推上去
```

## 三、日常命令速查

| 目的 | 命令 |
|---|---|
| 看状态 | `git status` |
| 看差异 | `git diff` / `git diff --staged` |
| 提交 | `git add -A` → `git commit -m "..."` |
| 推送 | `git push` |
| 历史（图形化） | `git log --oneline --graph --all` |
| 撤销工作区修改 | `git restore <文件>` |
| 撤销暂存 | `git restore --staged <文件>` |
| 改上一次提交信息 | `git commit --amend -m "新信息"` |
| 回退到某次提交（保留改动） | `git reset --soft <commit>` |
| 打里程碑标签 | `git tag -a v0.1-cli -m "命令行版完成"` → `git push --tags` |

## 四、提交信息规范（写进报告也好看）

```
feat:     新功能
fix:      修 bug
refactor: 重构（不改行为）
docs:     文档
test:     测试
chore:    构建/配置
```

例：`feat(frontier): 支持最佳优先策略与优先级函数`

建议的里程碑标签：

| 标签 | 对应阶段 |
|---|---|
| `v0.1-cli` | 第 1 周：命令行最小爬虫跑通 |
| `v0.2-core` | 第 2 周：抽取/入库/三策略/并发完成 |
| `v0.9-gui` | 第 3 周：GUI 可用 |
| `v1.0` | 第 4 周：测试与实验数据齐全，可演示 |

## 五、用 Issues 记进度（课程目标 7 的证据）

建 4 个 Issue，标题直接写周任务，例如：

- `[W1] 命令行爬虫：抓取/去重/深度限制`
- `[W2] 六字段抽取与 SQLite 落库`
- `[W3] GUI 与稳定性专项`
- `[W4] 三策略对比实验`

每完成一项就 Close，并在提交信息里写 `Refs #3`。最后截图 Issue 列表 = 进度管理证据。

## 六、常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `Repository not found` | 仓库名/用户名写错，或私有库未授权 | `git remote -v` 核对；重新 `git credential-manager configure` 登录 |
| `Failed to connect ... 443` 超时 | 网络被墙/代理未生效 | 开代理后 `git config --global http.proxy http://127.0.0.1:端口`（用完 `--unset` 清掉） |
| `Updates were rejected` | 远端有你没有的提交（比如网页上建库勾了 README） | `git pull --rebase origin main` 再 `git push` |
| 误把 `.venv` 提交了 | `.gitignore` 之前就 add 过 | `git rm -r --cached .venv` → `git commit -m "chore: 移除虚拟环境"` |
| 中文文件名显示成 `\344\270\255` | git 默认转义 | `git config --global core.quotepath false`（本仓库已设） |
| 提交没算到我的贡献图 | 提交邮箱不是 GitHub 账号绑定邮箱 | 在 GitHub → Settings → Emails 里绑定 `2490345331@qq.com`，或用 `git config user.email "你的ID@users.noreply.github.com"` |

## 七、提交前检查清单

- [ ] `git status` 里没有 `.venv/`、`data/*.db`、`logs/*.log`
- [ ] 代码能跑（至少 `python -c "import crawler"` 不报错）
- [ ] 没有硬编码的密钥/令牌
- [ ] 提交信息能看懂（一周后你自己也要靠它回忆）
