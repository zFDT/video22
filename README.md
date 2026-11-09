# 多平台内容采集 & 自动化创作工作流

自动化从小红书、抖音、微博等平台采集热门素材，经过整理分析后生成图文/视频内容的完整工作流。

## 功能概览

```
素材采集 → 整理去重 → 选题分析 → 文案生成 → 图文/视频生成
```

- 多平台并行采集（小红书、抖音、微博）
- 按话题自动分类、去重、热度排序
- AI 驱动的选题分析和文案生成
- 自动生成配图和短视频
- 支持定时任务自动化运行

## 话题方向

话题通过 `config/topics.json` 可配置，默认示例：

- FDM 3D 打印
- 示例话题二

你可以按需增删话题、关键词与目标平台。

## 环境要求

- Python 3.12+（推荐使用 Conda）
- Chrome 浏览器（用于 Cookie 获取）
- Node.js（用于 Skills CLI）

## 快速开始

### 1. 创建虚拟环境

```bash
conda create -n video22 python=3.12 -y
conda activate video22
pip install -r requirements.txt
```

### 2. 配置平台 Cookie

```bash
# 小红书 - 使用已有的登录工具
D:\go\xiaohongshu-mcp-windows-amd64\xiaohongshu-login-windows-amd64.exe

# 抖音 - 使用 Selenium 自动获取
python scripts/douyin_login.py
```

### 3. 配置文件

复制模板并填入你的配置：
```bash
copy config\platforms.example.json config\platforms.json
```

编辑 `config/platforms.json`，填入 Cookie 路径。

### 4. 运行

```bash
# 全流程执行
python scripts/main.py

# 仅采集
python scripts/main.py --collect

# 仅整理
python scripts/main.py --organize

# 仅生成内容
python scripts/main.py --generate

# 指定话题
python scripts/main.py --topic fdm_3d_printing
```

## 项目结构

```
├── config/                     # 配置文件
│   ├── topics.json             # 话题关键词配置
│   ├── platforms.json          # 平台认证配置（不入库）
│   ├── platforms.example.json  # 平台配置模板
│   └── generation.json         # 内容生成配置
├── scripts/
│   ├── main.py                 # 主入口（全流程编排）
│   ├── douyin_login.py         # 抖音 Cookie 获取工具
│   ├── get_cookies.py          # 通用 Cookie 获取工具
│   ├── collector/              # 采集器模块
│   │   ├── base_collector.py   # 采集器基类
│   │   ├── xhs_collector.py   # 小红书采集器
│   │   ├── douyin_collector.py # 抖音采集器
│   │   └── weibo_collector.py  # 微博采集器
│   ├── organizer/              # 素材整理模块
│   │   └── material_organizer.py
│   └── generator/              # 内容生成模块
│       └── content_generator.py
├── materials/                  # 素材库
│   ├── raw/                    # 原始采集数据（不入库）
│   └── organized/              # 整理后的素材
├── output/                     # 生成的成品
│   ├── images/
│   ├── videos/
│   └── posts/
├── logs/                       # 运行日志
├── requirements.txt
└── README.md
```

## 已安装的 Skills

| 类别 | Skill | 用途 |
|------|-------|------|
| 采集 | xiaohongshu | 小红书内容采集 |
| 采集 | douyin | 抖音内容采集 |
| 采集 | weibo-hot-search | 微博热搜 |
| 采集 | weibo_hotspot_analyzer | 微博热点分析 |
| 分析 | topic-analysis | 话题趋势分析 |
| 文案 | copywriting-skills | 小红书风格文案 |
| 文案 | copywriting | 通用营销文案 |
| 生成 | ai-image-generation | AI 图片生成 |
| 生成 | ai-video-generation | AI 视频生成 |
| 生成 | video-generation | 字节视频生成 (deer-flow) |
| 生成 | xiaohongshu-cover-generator | 小红书封面 |
| 生成 | xiaohongshu-images | 小红书配图 |

## 定时任务

### Windows 任务计划程序

```bash
# 每天早上 9 点执行采集
schtasks /create /tn "VideoCollect" /tr "D:\anaconda3\envs\video22\python.exe d:\视频22\scripts\main.py --collect" /sc daily /st 09:00
```

### Claude Code 定时触发

```bash
# 通过 /schedule 设置定时分析和生成
```

## Cookie 刷新

Cookie 会过期，需要定期刷新：

```bash
# 小红书（使用 exe 工具，会打开浏览器扫码登录）
D:\go\xiaohongshu-mcp-windows-amd64\xiaohongshu-login-windows-amd64.exe

# 抖音（使用 Selenium，会打开浏览器登录）
python scripts/douyin_login.py
```

## 注意事项

- 采集频率请遵守各平台规则，避免被封号
- Cookie 属于敏感信息，已在 .gitignore 中排除
- 微博搜索接口需要登录，当前仅支持公开热搜
- 小红书和抖音的 API 有反爬签名机制，建议配合 xiaohongshu-mcp 使用

## 技术特色与复盘

### 技术亮点

- **多平台采集器抽象**：`collector/base_collector.py` 定义了统一的采集基类，小红书、抖音、微博三个采集器分别继承并实现平台差异化的抓取与解析逻辑，形成清晰的策略模式，新增平台只需实现对应子类即可接入，无需改动编排层。
- **AI 驱动全链路**：从素材采集后的去重分类，到选题分析、文案生成，再到图文/视频成品输出，整条流水线由 AI 与 Skills CLI 串联，减少人工干预。
- **可配置话题体系**：通过 `config/topics.json` 集中管理话题、关键词与目标平台，支持多话题并行采集与分析，扩展新话题无需改代码。

### 个人贡献

独立完成该项目从 0 到 1 的设计与实现，包括：

- 设计并实现「采集 → 处理 → 生成」的内容自动化流水线架构；
- 抽象多平台采集器基类，落地小红书、抖音、微博三端采集能力；
- 接入 AI 选题分析与内容生成，并打通定时任务自动化运行。

### 收获与规划

- **收获**：完整实践了内容工程化的全流程，理解了如何用「抽象基类 + 策略模式」应对多平台差异，以及如何将 AI 能力嵌入到稳定的自动化工作流中。
- **后续规划**：扩展更多内容平台（如 B 站、视频号），接入更多 LLM 与生成模型，进一步优化去重与选题质量，提升内容产出的自动化程度与可维护性。
