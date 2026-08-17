# TodoCheckpointDraft — P2 完成（2026-08-18）

## 当前 todo / 活动切片

- 当前切片: P2 LangGraph 核心（已完成）
- 已完成: P0 ✅(9e6fee5) P1 ✅(4348526) P2 ✅
- 下一步: P3 Tools 体系

## P2 交付内容

- core/llm 多供应商层: schemas / base(LLMProvider) / providers(openai_compat 万能适配、mock、anthropic、gemini、ollama、azure) / factory(注册表+自动降级)
- agents 编排层: state(NovelState) / events(SSE 协议 8 类事件) / runner(GraphRunner: astream updates→事件桥接 + agent_runs 入库)
- 三条图: setting_graph(assemble→路由→7生成节点→consistency→persist)、chapter_graph(retrieve→write流式→review→rewrite循环→persist)、review_graph(Send 并行 8 维→聚合)
- nodes 迁移: 旧 Creative/Writer/Review 提示词与任务构造全部迁入 nodes/common.py；**旧 5 个 legacy Agent 文件删除**
- 服务切换: setting/writing/review service 的 AI 执行全部走图（单一执行路径，无并行残留）
- 新增: /api/agents/chat(SSE) + /run + /runs；agent_runs 表(M13)；搜索摘要统一到 SearchService(core/llm)
- 测试: tests/test_graphs.py（setting 持久化 / chapter 重写循环 / review 并行）+ conftest(临时DB+强制mock)

## 过程中发现并修复的 Bug

1. LangGraph v1 节点返回值只能含 state 字段（多余键被静默丢弃）→ Send spike 发现
2. with_structured 传 {"type":"json_object"} 无效 → 改用 response_format 绑定 + 兼容实现
3. messages() 返回 list 误传给 acomplete/astream（需 LLMRequest 包装）
4. **图节点会话未 commit 导致事务回滚**（assemble 可读、persist 必须 commit）→ setting/chapter 持久化节点补 commit；runner 的 agent_runs 同病同修
5. 重写循环缺 revision_round 递增 → 无限循环到 recursion limit；write_draft 现递增 + should_rewrite 加"无草稿即 persist"守卫

## 证据

- pytest 5 passed（parity 2 + graphs 3）
- e2e mock 冒烟: setting world/character 200+saved、chapter generate/continue/polish 200、SSE 事件齐全(token×387/node/review/checkpoint/done)、review 单维/综合 200、agents/run 并行维度 {logic,pacing}、agents/chat 8 事件、runs 入库 completed
- 真实环境路径: factory 从 settings.llm 解析用户 .env 的 MiMo(openai 兼容) 端点

## 漂移检查（DriftCheckDraft）

- 范围: 未越界；兼容边界: 现有 REST 路径不变（generate-stream 事件协议升级为类型化，P7 前端适配）
- 退休: legacy agents 全部删除 ✅；agent_factory 删除 ✅
- 决策: continue

## 恢复提示（ResumeStateHint）

- 恢复点: P3 Tools 体系（BaseTool/ToolRegistry/内置工具/web_search+knowledge_retrieve+setting_query 等/图绑定白名单/tool 事件）
