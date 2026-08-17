# TaskIntentDraft — NovelAI Writer 重构（LangGraph 多 Agent 编排 + 模块化能力栈）

- 日期: 2026-08-18
- 状态: active
- 目标（requested outcome）: 将 NovelAI Writer 重构为 LangGraph v1 多 Agent 编排 + 分层架构（API 薄层 / Service / 编排层 / 能力层 core: llm, tools, search, knowledge, mcp, skills），支持多模型供应商、Tools 注册表、网络搜索多后端降级、知识库（文档向量化 + 热梗/兵器/角色/世界观）、MCP 双向接入、Skills 目录化接入。
- 范围（scope）: backend 全面重构（P0-P6、P8）+ 前端轻量适配（P7 SSE 事件消费 + 新页面）。
- 非目标（non-goals）: 不引入用户认证；不更换技术栈（保留 FastAPI + Vue3 + SQLite）；不做 12 张存量表破坏性迁移。
- 风险提示: LangGraph v1 API 差异；chromadb × Python 3.13 兼容；22 处前后端失配修复回归；无 Key 时必须保持 mock 可用。

## 基线读取集（BaselineReadSet）

- backend/app/agents/*（agent_base / creative / writer / review / search）— 生成逻辑与提示词来源
- backend/app/api/*（projects / settings / writing / review / search）— 端点契约与 22 处失配来源
- backend/app/models/*（12 表）— 数据契约
- backend/app/config.py → 已迁移为 app/config/（settings.py）
- frontend/src/api/index.js — 前端 API 契约（对照测试基准）
- docs/02_架构设计文档_v2.md、.mimocode/plans/1785339790453-witty-eagle.md — 历史设计/失配清单
- backend/mcp/server.py — MCP 重建基准

## 基线使用状态（BaselineUsageDraft）

- 已读取: agents/*（全部）、api/*（全部）、models 结构、frontend/src/api/index.js、docs 02、mcp/server.py、config、requirements、.env.example、docker-compose、Dockerfile、gitignore
- 缺失: 无（docs/01、03、04 未读，P8 文档更新时再读）
- 决策: 已批准计划（exit_plan_mode approval）即为执行基线

## 影响声明（ImpactStatementDraft）

- 兼容边界: 现有 REST 端点路径不变（仅修复失配、新增端点）；12 存量表结构不变；前端 api/index.js 契约不变
- 退休边界: 旧 `app/agents/*` 5 个伪 Agent 文件在 P2 节点迁移完成后删除；`app/config.py` 已在 P0 删除（迁移至包）；`backend/mcp/` 旧 mock server 在 P5 删除
- 新增 owner: app/core/*（llm/tools/search/knowledge/mcp/skills）、app/agents/graphs、app/services/*
