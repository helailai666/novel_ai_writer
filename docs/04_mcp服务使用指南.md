# NovelAI Writer MCP 服务 — 使用指南

> **24个 MCP 工具**已注册到 AstrBot，可通过飞书直接控制小说创作全流程。

---

## 🚀 MCP 服务启动

```bash
# 方式1：通过 AstrBot 自动管理（推荐）
已配置在 F:\app\astrbot\data\mcp_server.json

# 方式2：手动启动
cd D:\project\novel_ai_writer
python -m backend.mcp
```

## 📊 全部24个工具

### 📁 项目管理（3个）
| 工具 | 说明 | 在飞书说 |
|:----|:----|:---------|
| `create_project` | 创建项目 | "创建一本玄幻小说《xxx》" |
| `list_projects` | 列出项目 | "我的小说项目有哪些" |
| `get_project_progress` | 查询进度 | "《xxx》写到哪了" |

### 🌍 设定生成（4个）
| 工具 | 说明 |
|:----|:----|
| `generate_world_setting` | 世界观设定（时代/规则/地理） |
| `generate_characters` | 角色设定（主角/配角/反派） |
| `generate_items` | 道具体系（武器/防具/丹药） |
| `generate_outline` | 大纲生成（分卷+章节） |

### ✍️ 创作控制（2个）
| 工具 | 说明 |
|:----|:----|
| `generate_chapter` | 写单章（2000字） |
| `batch_generate_chapters` | 批量生成（连续章节） |

### 🌐 搜索参考（1个）
| 工具 | 说明 |
|:----|:----|
| `search_novel_reference` | 搜小说名→自动分析设定 |

### 📊 统计（1个）
| 工具 | 说明 |
|:----|:----|
| `get_statistics` | 字数/章节/角色统计 |

### 🔍 审核系统（8个）
| 工具 | 说明 | 检查内容 |
|:----|:----|:---------|
| `review_chapter` | 单章审核 | 设定+语法+通顺+文笔 |
| `review_batch_chapters` | 批量审核 | 多章质量评估 |
| `review_setting_consistency` | 设定一致性 | 角色/道具/世界观 vs 内容 |
| `review_continuity` | 连贯性 | 剧情衔接/时间线 |
| `review_grammar` | 语法检查 | 错别字/病句/语感 |
| `review_foreshadowing` | 伏笔追踪 | 设置与回收情况 |
| `review_pacing` | 节奏分析 | 爽点/冲突/高潮密度 |
| `generate_review_report` | 审校报告 | 综合评分卡 |

---

## 🎯 飞书对话示例

```bash
🤖 → 机蛋儿，创建一本玄幻小说《剑破九天》
📋 → ✅ 项目已创建！项目ID: proj_001

🤖 → 机蛋儿，搜索参考《凡人修仙传》的设定
🌐 → ✅ 分析完成！已自动填充世界观/角色/道具/大纲

🤖 → 机蛋儿，生成大纲 100章分5卷
📖 → ✅ 5卷100章大纲已生成

🤖 → 机蛋儿，写第1章 2000字
✍️ → ✅ 第1章「初入仙途」已生成

🤖 → 机蛋儿，审核第1章
🔍 → ✅ 设定一致/语法通过/文笔评分82
```

---

## 📂 文件位置

| 文件 | 路径 |
|:----|:-----|
| MCP Server | `D:\project\novel_ai_writer\backend\mcp\server.py` |
| AstrBot 配置 | `F:\app\astrbot\data\mcp_server.json` |
| MCP 启动 | `python -m backend.mcp` |
