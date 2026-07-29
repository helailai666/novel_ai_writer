# NovelAI Writer — AI 辅助小说创作平台 🚀

> 基于 LangChain + FastAPI + Vue 3 的全栈 AI 写小说工具

---

## ✨ 核心功能

| 功能 | 说明 |
|:----|:------|
| 📝 **完整创作流程** | 类型→世界观→角色→能力→道具→大纲→章节→审核 |
| 🤖 **6个AI Agent** | Master / Creative / Writer / Review / Search / World |
| 🌐 **网络搜索** | 输入小说名自动分析设定（Tavily + DuckDuckGo） |
| 🎨 **打字机效果** | SSE 流式输出，逐字展示生成内容 |
| 🔍 **8维审核系统** | 设定一致性/伏笔追踪/节奏分析/文笔评估等 |
| 🔌 **MCP 协议** | 24个工具注册 AstrBot，飞书直接控制创作 |
| 🐳 **Docker 部署** | docker-compose up 一键启动 |

---

## 🏗️ 系统架构

```
用户 (浏览器:5173 / 飞书:MCP)
    │
    ├── Frontend (Vue 3 + Naive UI)
    │       │ axios /api/*
    │       ▼
    ├── Backend (FastAPI :8000)
    │       │
    │       ├── API 层 ─── settings.py / writing.py / review.py / search.py
    │       ├── Agent 层 ─ 6个 LangChain Agent
    │       ├── 数据层 ─── SQLite (12张表)
    │       └── MCP Server ─ 注册到 AstrBot
    │
    └── MCP 协议 ──→ 机蛋儿直接控制：创建/设定/写作/审核
```

---

## 🚀 快速启动

### 方式 1：一键启动（推荐）

```bash
# Windows
双击 start-dev.bat

# macOS / Linux
chmod +x start-dev.sh && ./start-dev.sh
```

### 方式 2：手动启动

```bash
# 终端1：后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs

# 终端2：前端
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 方式 3：Docker 部署

```bash
# 复制配置
cp .env.example .env
# 编辑 .env 填入 API Key（可选）

# 一键部署
docker-compose up -d
# → http://localhost:5173
```

---

## 🎯 使用示例

### 通过 Web 界面
1. 打开 `http://localhost:5173`
2. 点击「新建项目」→ 输入小说名、选择类型
3. 在「设定」页面：点击 AI 生成世界观/角色/道具
4. 在「创作」页面：输入章节号，点击生成
5. 在「审核」页面：运行各维度审核

### 通过飞书 MCP 对话
```
机蛋儿，创建一本玄幻小说《剑破九天》
机蛋儿，生成这本小说的世界观
机蛋儿，设计5个角色，主角叫林玄
机蛋儿，生成大纲，100章分5卷
机蛋儿，写第1章
机蛋儿，审核第1章
```

---

## 📁 项目结构

```
novel_ai_writer/
├── backend/             # FastAPI 后端
│   ├── app/
│   │   ├── api/         # 4组API路由（30+端点）
│   │   ├── agents/      # 6个LangChain Agent
│   │   ├── models/      # 12张数据库表
│   │   └── services/    # 搜索/导出服务
│   ├── mcp/             # MCP Server（24个工具）
│   └── requirements.txt
├── frontend/            # Vue 3 前端
│   ├── src/
│   │   ├── views/       # 4个页面
│   │   ├── components/  # Layout + StreamOutput
│   │   └── api/         # Axios封装
│   └── package.json
├── docs/                # 完整需求/架构文档
├── docker-compose.yml   # 一键部署
├── start-dev.bat        # Windows启动
└── start-dev.sh         # Mac/Linux启动
```

---

## ⚙️ 环境变量

```bash
# LLM 配置（至少配一个，不配则用 Mock）
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
LLM_PROVIDER=openai          # openai / deepseek / ollama
LLM_MODEL=gpt-4o-mini

# 搜索配置（可选，不配则用 DuckDuckGo）
TAVILY_API_KEY=tvly-xxx
```

> 💡 **无需 API Key 也能用！** 所有 AI 功能自动降级到 Mock 模式。

---

## 📊 技术栈

| 层级 | 技术 | 版本 |
|:----|:----|:----:|
| 前端框架 | Vue 3 + Vite | ^3.4 |
| UI 组件库 | Naive UI | ^2.38 |
| 后端框架 | FastAPI | ^0.110 |
| AI 框架 | LangChain | ^0.1 |
| 数据库 | SQLite → PostgreSQL | - |
| 搜索 | Tavily / DuckDuckGo | - |
| 部署 | Docker Compose | - |
| MCP | Model Context Protocol | - |

---

## 📈 开发路线图

| 阶段 | 状态 | 内容 |
|:----|:----:|:----|
| Phase 1 🏗️ | ✅ 完成 | 项目骨架：FastAPI + Vue3 + DB + MCP |
| Phase 2 🤖 | ✅ 完成 | AI Agent：Creative/Writer/Review/Search |
| Phase 3 🔗 | ✅ 完成 | 前后端联调 + Pinia + 无Mock |
| Phase 4 🐳 | ✅ 完成 | Docker + SSE流式 + 一键启动 |

---

## 📄 License

MIT
