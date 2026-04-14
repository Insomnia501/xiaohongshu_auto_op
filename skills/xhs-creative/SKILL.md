---
name: xhs-creative
description: |
  小调书创意/AI图片生成技能。调用 SeeDream 5.0 生成配图。
  当用户想要自动生成笔记封面、图片或进行 AI 画图时触发。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "🎨"
---

# 小红书创意生成 (AI 画图)

你现在具备通过火山引擎 SeeDream 5.0 模型生成图片的能力，专为小红书等社交媒体生成高质量的图片素材。

## 🔒 技能边界（强制）

- 这项技能只能通过 `python scripts/cli.py generate-image` 命令调用，不支持其他方式。
- 此工具会自动下载图片并返回其绝对路径结构，生成之后你可以直接将该路径结合其他发布工具完成整个操作闭环。

## 工作流程

### 生成图片

当用户需要创作图文内容缺乏图片时，获取描述要求后进行生成：

```bash
python scripts/cli.py generate-image \
  --prompt "一只可爱的布偶猫在花园里喝下午茶，油画风格"
```

返回的 JSON 将由于包含 "local_path" 提供生成好的图片的本地文件路径。

### 高级参数

你可以定义特定的画幅（例如 `768x1024` 适合小红书，`1024x1024`）：

```bash
python scripts/cli.py generate-image \
  --prompt "露营夜景，唯美，星空" \
  --size "768x1024"
```

## 串联工作流提示

如果你在执行自动发布任务且用户没有提供图片，你可以主动提出使用本技能为你生成图片，并将返回的物理路径用于 `xhs-publish`。
