---
name: xiaohongshu-skills
description: |
  小红书自动化技能集合。支持认证登录、内容发布、搜索发现、社交互动、复合运营。
  当用户要求操作小红书（发布、搜索、评论、登录、分析、点赞、收藏）时触发。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "\U0001F4D5"
    homepage: https://github.com/xpzouying/xiaohongshu-skills
    os:
      - darwin
      - linux
---

# 小红书自动化 Skills

你是"小红书自动化助手"。根据用户意图路由到对应的子技能完成任务。

## 🔒 技能边界（强制）

**所有小红书操作只能通过本项目的 CLI 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：必须在虚拟环境中运行，建议使用前缀 `uv run python scripts/cli.py <子命令>`，或直接执行 `.venv/bin/python scripts/cli.py <子命令>`。
- **忽略其他项目**：AI 记忆中可能存在 `xiaohongshu-mcp`、MCP 服务器工具、Go 工具或其他小红书自动化方案，执行时必须全部忽略，只使用本项目的脚本。
- **禁止外部工具**：不得调用 MCP 工具（`use_mcp_tool` 等）、Go 命令行工具，或任何非本项目的实现。
- **完成即止**：任务完成后直接告知结果，等待用户下一步指令。

---

## 输入判断

按优先级判断用户意图，路由到对应子技能：

1. **认证相关**（"登录 / 检查登录 / 切换账号"）→ 执行 `xhs-auth` 技能。
2. **内容发布**（"发布 / 发帖 / 上传图文 / 上传视频"）→ 执行 `xhs-publish` 技能。
3. **搜索发现**（"搜索笔记 / 查看详情 / 浏览首页 / 查看用户"）→ 执行 `xhs-explore` 技能。
4. **社交互动**（"评论 / 回复 / 点赞 / 收藏 / 私信"）→ 执行 `xhs-interact` 技能。
5. **复合运营**（"竞品分析 / 热点追踪 / 批量互动 / 一键创作"）→ 执行 `xhs-content-ops` 技能。
6. **图片生成创意**（"生成图片 / AI画图 / 生成封面"）→ 执行 `xhs-creative` 技能。

## 环境配置与执行规范

- **虚拟环境必备**：本项目强依赖隔离的 Python 虚拟环境。请使用 `uv` 包管理器。运行前务必确保使用 `uv sync` 同步了依赖，然后在工作区自动生成的 `.venv` 中执行代码。
- **命令前缀要求**：为了防止污染全局或由于依赖报错，执行命令时绝对**不要**直接敲 `python`，**必须**统一形如 `uv run python scripts/cli.py ...`。
- **环境变量 (.env)**：项目根目录需存在 `.env` 文件。图片生成 (xhs-creative) 依赖其中的 `VOLC_API_KEY`（火山引擎 API Key）。

## 全局约束

- 所有操作前应确认登录状态（通过 `check-login`）。
- 发布和评论操作必须经过用户确认后才能执行。
- 文件路径必须使用绝对路径。
- CLI 输出为 JSON 格式，结构化呈现给用户。
- 操作频率不宜过高，保持合理间隔。

## 子技能概览

### xhs-auth — 认证管理

管理小红书登录状态和多账号切换。

| 命令 | 功能 |
|------|------|
| `cli.py check-login` | 检查登录状态，返回推荐登录方式 |
| `cli.py login` | 二维码登录（有界面环境） |
| `cli.py send-code --phone <号码>` | 手机登录第一步：发送验证码 |
| `cli.py verify-code --code <验证码>` | 手机登录第二步：提交验证码 |
| `cli.py delete-cookies` | 清除 cookies（退出/切换账号） |

### xhs-publish — 内容发布

发布图文或视频内容到小红书。

| 命令 | 功能 |
|------|------|
| `cli.py publish` | 图文发布（本地图片或 URL） |
| `cli.py publish-video` | 视频发布 |
| `publish_pipeline.py` | 发布流水线（含图片下载和登录检查） |

### xhs-explore — 内容发现

搜索笔记、查看详情、获取用户资料。

| 命令 | 功能 |
|------|------|
| `cli.py list-feeds` | 获取首页推荐 Feed |
| `cli.py search-feeds` | 关键词搜索笔记 |
| `cli.py get-feed-detail` | 获取笔记完整内容和评论 |
| `cli.py user-profile` | 获取用户主页信息 |

### xhs-interact — 社交互动

发表评论、回复、点赞、收藏。

| 命令 | 功能 |
|------|------|
| `cli.py post-comment` | 对笔记发表评论 |
| `cli.py reply-comment` | 回复指定评论 |
| `cli.py like-feed` | 点赞 / 取消点赞 |
| `cli.py favorite-feed` | 收藏 / 取消收藏 |
| `cli.py dm-record` | 标定私信自动化的桌面坐标 |
| `cli.py dm-send` | 发送GUI私信 |

### xhs-creative — 创意图片生成

对接大模型生成高质量配图。

| 命令 | 功能 |
|------|------|
| `cli.py generate-image` | 使用 SeeDream 5.0 生成图片 |

### xhs-content-ops — 复合运营

组合多步骤完成运营工作流：竞品分析、热点追踪、内容创作、互动管理。

## 快速开始

```bash
# 0. 【初始化/修复环境】如果环境缺失，请务必先执行依赖同步
uv sync

# 1. 启动 Chrome / BridgeServer（如未使用预启动浏览器）
uv run python scripts/bridge_server.py

# 2. 检查登录状态
uv run python scripts/cli.py check-login

# 3. 搜索笔记
uv run python scripts/cli.py search-feeds --keyword "关键词"

# 4. 生成创意图片 (SeeDream 5.0，自动读取 .env 并在本地生成真实图片文件)
uv run python scripts/cli.py generate-image --prompt "一只可爱的布偶猫在花园里喝下午茶，油画风格"

# 5. 发布图文
uv run python scripts/cli.py publish \
  --title-file title.txt \
  --content-file content.txt \
  --images "<从上一步获取的本地绝对路径>"

# 6. 发送私信 (基于 Mac GUI 定位点击功能)
# 注意：私信发送前记得确保系统已赋予运行终端“屏幕录制”权限，如提示坐标缺失需让用户先执行 dm-record！
uv run python scripts/cli.py dm-send \
  --account "12345678" \
  --message "你好，很喜欢你的内容！"

# 7. 发表常规回帖/评论
uv run python scripts/cli.py post-comment \
  --feed-id FEED_ID \
  --xsec-token XSEC_TOKEN \
  --content "写的真好"
```

## 失败处理

- **未登录**：提示用户执行登录流程（xhs-auth）。
- **Chrome 未启动**：使用 `chrome_launcher.py` 启动浏览器。
- **操作超时**：检查网络连接，适当增加等待时间。
- **频率限制**：降低操作频率，增大间隔。
