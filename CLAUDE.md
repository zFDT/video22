# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

多平台内容采集与自动化创作工作流。从小红书、抖音采集热门素材，整理分析后用 Claude 生成多平台文案。

话题方向：通过 config/topics.json 可配置（默认示例：FDM 3D 打印等）。

## 环境与运行

```bash
# 环境：Conda video22，Python 3.12
conda activate video22
pip install -r requirements.txt

# 全流程（采集 → 整理 → 生成）
python scripts/main.py

# 分步执行
python scripts/main.py --collect
python scripts/main.py --organize
python scripts/main.py --generate
python scripts/main.py --topic fdm_3d_printing
```

运行时会弹出两个 Chrome 窗口（小红书端口 9511，抖音端口 9512），首次需要手动登录，之后复用 `browser_data/` 中的 session。遇到验证码时脚本会暂停等待用户处理。

## 架构

### 数据流

```
浏览器采集(DrissionPage) → raw JSON + 媒体下载 → 整理去重排序 → Claude 生成文案 → output/posts/
```

### 核心模块

- **scripts/main.py** — 入口，编排全流程。启动两个独立浏览器实例并行采集，采集完关闭。
- **scripts/collector/** — 采集器。`BaseCollector` 定义接口（`search` + `collect` + `parse_result`），子类实现平台逻辑。两个采集器通过 `asyncio.gather` 并行执行。
- **scripts/organizer/** — 素材整理。按话题分类、去重（source_url）、热度排序，输出到 `materials/organized/`。
- **scripts/generator/** — 内容生成。调用 `claude --print -p "prompt"` 生成文案，保存为 JSON + 独立 .txt 文件。

### 浏览器管理

采集器使用 DrissionPage 控制 Chrome。关键设计：
- 每个平台独立端口（XHS: 9511, Douyin: 9512），避免实例冲突
- `browser_data/{platform}/` 持久化用户数据目录，登录状态跨次运行保留
- 流程开始时创建浏览器实例，注入到采集器中复用，结束时统一关闭
- 页面加载后检测验证码元素，暂停等待用户处理

### 配置

- `config/topics.json` — 话题关键词和平台映射
- `config/platforms.json` — 平台认证（cookies_json 路径），不入库
- `config/generation.json` — 文案风格、图片 prompt 参数

## 关键约定

- 采集器的 `search()` 方法是 async 的，但内部用 `time.sleep()` 做页面等待（DrissionPage 是同步的）
- `base_collector.collect()` 中用 `asyncio.sleep()` 做 rate limit，使并行采集不互相阻塞
- 媒体文件下载在 `save_results()` 中自动执行，保存到 `{platform}_{timestamp}_media/`
- 文案生成依赖 `claude` CLI（`claude --print -p`），需要当前环境有 Claude Code 可用
- 微博采集器已废弃（文件保留但未在 `__init__.py` 中导出）

## 敏感文件（不入库）

`config/platforms.json`、`config/douyin_cookies.json`、`browser_data/`、`services/xhs-mcp/cookies*.json`
