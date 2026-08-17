# TodoCheckpointDraft — P1 完成（2026-08-18）

## 当前 todo / 活动切片

- 当前切片: P1 目录分层 + Service 抽取（已完成，待提交）
- 已完成 todos: P0 ✅（9e6fee5）、P1 ✅
- 下一步: 提交 P1 → P2 LangGraph 核心

## P1 交付内容

- Service 层: project_service / setting_service（9 模块通用 CRUD + AI 生成）/ writing_service / review_service / agent_factory（统一 Agent 构造）
- API 薄层化: projects(155→~110 行) settings(662→~400 行) writing(441→~210 行) review(166→~80 行)；行为零变化
- 搜索统一: SearchAgent.search_raw → SearchService.search_web（删除两份重复 Tavily/DDG 实现与独立缓存）
- 修复: `/web/ai-summary` 双重搜索（缓存统一后自然消除）、`/web/cache/clear` 失效调用、**导出中文文件名 latin-1 500 崩溃（RFC 5987 filename*）**
- 新增: app/core/ 层骨架、app/deps.py、pytest.ini、tests/test_api_parity.py（路由↔前端对照测试，含 `${dimension}` 闭集展开）

## 证据

- `pytest tests/` → 2 passed（parity 全绿）
- mock 模式全链路冒烟: project/world/character CRUD、AI generate-world、volume/chapter、generate/continue/polish、review consistency+comprehensive、search web、export（中文名 200）、SSE stream（chunk/done/saved 事件齐全）、batch-generate(2)
- 22 处历史失配核对: 当前代码大多已修复（FK/CORS/body 传参等），对照测试建立防回归屏障

## 漂移检查（DriftCheckDraft）

- 范围: 未越界；兼容边界保持（端点路径/响应形状未变）
- 退休: search_agent 内部重复实现已删；app/agents/* 遗留至 P2 迁移
- 决策: continue

## 恢复提示（ResumeStateHint）

- 恢复点: 提交 P1 后进入 P2（LangGraph state/events/runner + 三条图 + nodes 迁移旧 Agent 逻辑 + /api/agents/chat SSE + agent_runs 表）
