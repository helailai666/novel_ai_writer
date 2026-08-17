# NovelAI Writer — AI 辅助小说创作平台 🚀

> 基于 **LangGraph + FastAPI + Vue 3** 的全栈 AI 写小说工具（v2 架构）

---

## ✨ 核心能力

| 能力 | 说明 |
|:----|:-----|
| 🧠 **LangGraph 多 Agent 编排** | 4 张图：设定生成 / 章节写作（含审核→修订循环）/ 8 维并行审核 / Supervisor 自由对话路由 |
| 🤖 **多模型供应商** | openai / deepseek / qwen / glm / kimi / ollama / anthropic / gemini / azure / mock，OpenAI 兼容万能适配 |
| 🛠️ **工具注册表（10 个内置工具）** | 网络搜索 / 设定查询 / 角色·兵器·世界观·伏笔查询 / 知识库检索 / 热梗查询 / 章节读取 / 项目摘要 |
| 🌐 **网络搜索多后端** | Tavily / DuckDuckGo / Bing / SearXNG / Bocha，auto 模式自动降级 |
| 📚 **知识库** | 文档切片 + 向量化（Chroma）+ 混合检索（关键词 ∪ 向量）；热梗 / 兵器 / 角色 / 世界观分类 |
| 🔌 **MCP 双向接入** | 服务端暴露真实创作工具（stdio/SSE）；客户端桥接外部 MCP server 工具进 Agent |
| 🎯 **Skills 技能包** | 目录化技能（网文标准 / 人物弧光 / 伏笔管理 / 节奏控制 / 文笔润色 / 玄幻专项），注入 system prompt 与工具白名单 |
| 🎨 **类型化 SSE 流式** | node / token / tool_call / review / checkpoint / done 事件协议，前端活动日志实时展示 |
| 🐳 **Docker 部署** | docker-compose up 一键启动 |

---

## 🏗️ 系统架构（v2）

```
用户 (浏览器:5173 / 飞书·外部客户端:MCP)
    │
    ├── 前端 (Vue 3 + Naive UI) ── axios /api/* + SSE
    │
    ├── API 薄层 (FastAPI :8000)  ── 校验 + 调 Service，无业务逻辑
    │       └── app/api/*: projects/settings/writing/review/search/agents/tools/knowledge/hot-memes/mcp/skills/model-providers
    │
    ├── Service 层 ── 项目 / 设定 / 写作 / 审核 / 知识库（事务边界）
    │
    ├── 编排层 (LangGraph) ── state / events / runner / 4 图 / 节点
    │       ├── setting_graph   设定生成（assemble→路由→generate→一致性→persist）
    │       ├── chapter_graph   写作（retrieve→write 流式→review→rewrite 循环→persist）
    │       ├── review_graph    8 维并行审核（Send fan-out→聚合）
    │       └── chat_graph      Supervisor 自由文本→自动路由子图
    │
    ├── 能力层 (app/core) ── 可插拔基础能力
    │       ├── llm/      多供应商工厂（OpenAI 兼容万能适配 + 专用适配 + Mock）
    │       ├── tools/    工具抽象 + 注册表 + 10 内置工具 + 外部桥接
    │       ├── search/   搜索后端路由与降级（含缓存）
    │       ├── knowledge/ 嵌入 + 向量存储(Chroma/Mock) + 切片索引 + 混合检索
    │       ├── mcp/      服务端(MCPServer) + 客户端桥接
    │       └── skills/   技能包加载/注册/注入
    │
    └── 数据层 ── SQLAlchemy 16 表 + Alembic 迁移 + Chroma 向量库
```

---

## 🚀 快速启动

### 方式 1：本地开发

```bash
# 后端（Python 3.12+）
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env            # 填入 API Key（可选，无 Key 自动 Mock）
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs

# 前端
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 方式 2：Docker 部署

```bash
cp .env.example .env
docker-compose up -d
# → http://localhost:5173
```

### MCP Server（可选）

```bash
cd backend && python -m app.core.mcp.server            # stdio
cd backend && python -m app.core.mcp.server --sse      # SSE :8765
```

---

## 🔌 配置（.env）

```bash
# ── LLM（至少配一个，不配则 Mock）──────────────────────
LLM_PROVIDER=deepseek        # openai/deepseek/ollama/azure/anthropic/gemini/qwen/glm/kimi/mock
LLM_MODEL=deepseek-chat
LLM_API_KEY=
LLM_API_BASE=https://api.deepseek.com
# 各供应商独立 Key: OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / DASHSCOPE_API_KEY / ZHIPU_API_KEY / MOONSHOT_API_KEY

# ── 搜索 ──────────────────────────────────────────────
SEARCH_PROVIDER=auto         # auto/tavily/duckduckgo/bing/searxng/bocha/mock
TAVILY_API_KEY=

# ── 向量化（可选，默认 Mock 哈希向量）──────────────────
EMBEDDING_PROVIDER=mock      # openai/local/mock
VECTOR_STORE_BACKEND=chroma  # chroma/faiss/mock

# ── Agent 编排 ────────────────────────────────────────
AGENT_MAX_REVISIONS=2        # 章节写作图最大修订轮数
AGENT_REVIEW_THRESHOLD=75    # 低于该分触发重写
```

> 💡 **无需任何 API Key 也能用**：LLM / 搜索 / 嵌入 / 向量全部自动降级 Mock。

---

## 📖 使用示例

### 通过 Web 界面
1. 新建项目 → 在「模块设定」AI 生成世界观/角色/道具
2. 「创作工作台」流式生成章节（活动日志可见工具调用与审核评分）
3. 「知识库」导入参考文档 / 「热梗库」管理流行语（写作时自动注入）
4. 「审核视图」8 维并行审核
5. 「全局设置」切换模型供应商并测试连通、查看技能包与 MCP 状态

### 通过 Agent 对话（/api/agents/chat 或 Supervisor chat 图）
```json
POST /api/agents/chat
{"graph": "chat", "project_id": "…", "task": "帮我生成世界观设定",
 "skills": ["webnovel-standards", "genre-xuanhuan"]}
```

### 通过 MCP（外部客户端）
```
mcpServers: {
  "novel-writer": {"command": "python", "args": ["-m", "app.core.mcp.server"], "cwd": "<backend路径>"}
}
```
可用工具（真实执行）：setting_query / knowledge_retrieve / hot_meme_lookup / web_search / weapon_lookup / character_lookup / world_setting_lookup / foreshadow_query / chapter_get / project_summary

---

## 📁 项目结构（要点）

```
backend/
├── app/
│   ├── api/            # 11 组薄路由
│   ├── services/       # 业务服务层
│   ├── agents/         # LangGraph: state/events/runner/graphs(4图)/nodes
│   ├── core/           # 能力层: llm/tools/search/knowledge/mcp/skills
│   ├── models/         # 16 张表
│   └── config/         # 分层配置
├── migrations/         # Alembic 迁移
├── skills/             # 内置技能包（6 个）
├── config/             # mcp_servers.yaml
└── tests/              # 27 项测试（parity/图/工具/知识库/MCP/技能）
frontend/
└── src/views/          # 10 个页面（含知识库/热梗/全局设置）
```

---

## 📄 License

MIT
