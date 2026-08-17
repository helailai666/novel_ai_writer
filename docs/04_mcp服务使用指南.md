# NovelAI Writer MCP 服务 — 使用指南（v2）

> 重构后 MCP 服务基于 **MCPServer + 工具注册表自动暴露**，全部真实执行（DB / 图 / 搜索），非 Mock。

---

## 🚀 MCP 服务启动

```bash
# 方式1：stdio（默认，供 Claude Desktop / AstrBot 等外部客户端）
cd backend
python -m app.core.mcp.server

# 方式2：SSE
python -m app.core.mcp.server --sse --host 127.0.0.1 --port 8765
```

## 注册到外部客户端

```json
{
  "mcpServers": {
    "novel-writer": {
      "command": "python",
      "args": ["-m", "app.core.mcp.server"],
      "cwd": "<backend 目录绝对路径>"
    }
  }
}
```

## 📊 可用工具（10 个，自动随注册表扩展）

| 工具 | 说明 |
|:----|:----|
| `project_summary` | 项目概况（类型/简介/各模块数量） |
| `setting_query` | 按关键词查询设定（世界观/角色/技能/道具/势力/大纲/场景/时间线/伏笔） |
| `chapter_get` | 读取指定章节标题与正文 |
| `character_lookup` | 角色设定查询（性格/背景/能力/关系） |
| `weapon_lookup` | 兵器（道具 weapon 类）查询 |
| `world_setting_lookup` | 世界观设定查询 |
| `foreshadow_query` | 伏笔查询（埋设/回收状态） |
| `knowledge_retrieve` | 知识库混合检索（文档/设定资料） |
| `hot_meme_lookup` | 热梗查询（含义 + 用法示例） |
| `web_search` | 网络搜索（多后端自动降级） |

> 工具名与参数 schema 由注册表自动生成：`/api/tools` 可查看最新清单。

## 🔌 外部 MCP Server 桥接（客户端模式）

本项目也可作为 **MCP 客户端**，把外部 server 的工具桥接进 Agent：

1. 复制 `backend/app/config/mcp_servers.example.yaml` → `backend/config/mcp_servers.yaml`
2. 启用要桥接的 server（`enabled: true`）
3. 启动后端时自动桥接；或调用 `POST /api/mcp/reload`

桥接后的工具以 `mcp_<server名>_<工具名>` 出现在工具注册表，Agent 可调用。

## 测试

```bash
cd backend && python -m pytest tests/test_mcp.py -v
```
