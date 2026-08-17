# TodoCheckpointDraft — P4 完成（2026-08-18）

## 当前 todo / 活动切片

- 当前切片: P4 知识库（已完成）
- 已完成: P0 ✅(9e6fee5) P1 ✅(4348526) P2 ✅(fd15535) P3 ✅(c225328) P4 ✅
- 下一步: P5 MCP 双向接入

## P4 交付内容

- 新表: knowledge_docs / knowledge_chunks / hot_memes（M14-M16）+ Alembic 迁移（0001，IF NOT EXISTS 幂等，存量库+全新库双验证）
- core/knowledge: embeddings(OpenAI兼容/Mock哈希向量) + vector_stores(Chroma/Mock余弦) + indexer(段落优先切片+向量化) + retriever(混合检索：ILIKE多词+CJK二元组 ∪ 向量TopK)
- KnowledgeService: 文档 CRUD/文本摄取/文件上传/检索 + 热梗 CRUD/搜索
- 工具: knowledge_retrieve + hot_meme_lookup（内置工具 8→10 个）
- API: /api/knowledge（CRUD+ingest+upload+search）、/api/hot-memes（CRUD+search）
- 写作图注入: retrieve_context 自动检索知识库+热梗 → 上下文（_context_text 渲染）

## 过程中修复

- Alembic: 异步 URL→同步转换（env.py）；sqlite 多语句单次执行报错→逐表 execute
- 类内方法遮蔽内置 list（list[str] 注解报错）→ 改名 get_all
- `"""doc""" ...` 同行语法错误 → 换行
- 中文检索无空格分词 → CJK 重叠二元组 OR 匹配

## 证据

- pytest 16 passed（parity2 + graphs3 + knowledge5 + tools6）
- Alembic: 存量库 12+4 表 + 全新库 4 表均验证
- 知识 API e2e: ingest→search→list→get→delete + 热梗 search 全通
- 写作图: 知识文档注入 retrieve_context 断言通过

## 漂移检查

- 范围: 未越界；兼容: 存量 REST 不变，仅新增端点
- 决策: continue

## 恢复提示

- 恢复点: P5 MCP（服务端重建暴露真实工具 / 客户端桥接外部 server / mcp_servers.yaml 配置 / pyproject 包路径修复）

# P5 完成（2026-08-18 追加）

- MCP 服务端重建: app/core/mcp/server.py（MCPServer + 注册表自动暴露 10 工具，代码生成带类型签名 handler，stdio/SSE 传输），删除旧 backend/mcp（与 SDK 包名冲突）
- MCP 客户端: app/core/mcp/client.py（stdio/SSE 桥接，工具命名 mcp_<server>_<tool>，每次调用独立建连）
- 配置: backend/config/mcp_servers.yaml（示例，默认全部 disabled）；启动时 lifespan 自动 bridge_all
- API: /api/mcp/servers + /api/mcp/reload + /api/mcp/tools
- 修复: mcp 2.0 移除 fastmcp→MCPServer；Tool.input_schema 属性名；抽象类实例化；代码生成参数顺序/初始化
- 测试: test_mcp.py 2 项（服务端 stdio 握手真实工具调用 / 客户端桥接 fake server）
- pytest 18 passed

# P6 完成（2026-08-18 追加）

- core/skills: models(SKILL.md frontmatter 解析) + registry(目录扫描) + runner(注入组装)
- 内置 6 技能包: webnovel-standards / character-arc / foreshadow-manager / pacing-control / prose-polish / genre-xuanhuan（backend/skills/）
- 图注入: state.skills → enhance_system(追加 system prompt) + skill_context(合并工具白名单)
- Supervisor 顶层对话图（chat 图）: 关键词分类（审核优先>设定>写作）→ 路由三条子图（子图作为节点嵌入）
- API: /api/skills（list/get/apply）；/api/agents/chat 支持 skills 字段
- 修复: SkillRegistry.list 遮蔽内置 list→get_all；分类优先级（"检查设定一致性"→review）
- 测试: test_skills.py 9 项（加载/注入/supervisor 路由/chat 图 e2e）
- pytest 27 passed

# P7 完成（2026-08-18 追加）

- 后端新增: /api/model-providers（供应商列表 + 连通性测试）
- 前端 api/index.js: +6 组 API（knowledge/hot-memes/agents/tools/skills/provider/mcp），修复重复 export default
- StreamOutput.vue: 类型化 SSE 事件消费（token/node/tool_call/review/checkpoint/done/error + 活动日志条 + 旧格式兼容）
- 新页面: KnowledgeView（文档列表/文本摄取/文件上传/混合检索抽屉）、HotMemesView（热梗卡片 CRUD+搜索）、GlobalSettingsView（供应商选择+连通测试/搜索模式/MCP 桥接状态/技能包网格）
- 路由: /projects/:id/knowledge + /projects/:id/memes + /settings；Layout 导航与面包屑更新
- 验证: npm run build 成功（新 chunk 生成）；parity 测试覆盖新增 API 调用全命中
- pytest 27 passed

# P8 完成（2026-08-18 追加）— 验收清单全部通过

## 验收清单（计划 §0 成功标准逐项）

1. ✅ 无 Key 全链路 Mock 可跑：设定生成→写章节→审核→知识检索→工具调用（验收冒烟全过）
2. ✅ LangGraph 4 图 + SSE 类型化事件（token/node_start/review/checkpoint/done 齐全）
3. ✅ 供应商 10 个 + /api/model-providers 列表与连通测试（mock 测试 ok）
4. ✅ 工具注册表 10 内置 + ReAct 工具循环 + tool_call/tool_result 事件
5. ✅ 知识库：摄取→切片→向量→混合检索命中；热梗/兵器/角色/世界观分类（写作图自动注入）
6. ✅ MCP 双向：服务端 stdio 握手真实工具（10 个）+ 客户端桥接外部 server（测试通过）
7. ✅ Skills：6 内置技能包加载/注入（system prompt + 工具白名单），supervisor chat 图
8. ✅ 前端路径兼容 + parity 测试覆盖新增 API 全命中；npm build 成功
9. ✅ pytest 27 passed

## P8 交付

- backend/Dockerfile 补 COPY skills/ + config/
- README.md 重写（v2 架构）、docs/05_重构后架构_v3.md、docs/04 MCP 指南更新
- .gitignore 加 data/（向量库）
- 验收冒烟脚本覆盖 11 项断言全过

## 最终漂移检查

- 范围: 全部 8 阶段完成；兼容边界保持（存量 REST 路径未变）
- 退休: legacy agents/config.py/backend-mcp 已删；旧文档 02 保留为历史
- Docker 沙箱不可用（docker 未安装）→ Dockerfile 静态核对通过，未实跑镜像
- 决策: 完成

## 恢复提示

- 无遗留阻塞；后续可扩展: supervisor LLM 分类、项目级技能绑定、faiss/qdrant 后端、Redis 缓存

# F 轮收尾（2026-08-18 追加）— 跟进项全部完成

1. ✅ setting 图 7 个 generate 节点接入 ReAct 工具循环（web_search/knowledge_retrieve/setting_query 白名单 + 技能注入）——补全计划 §4.2 承诺
2. ✅ test_api_integration.py 8 项（项目CRUD/AI生成/SSE类型事件/审核/chat路由/知识热梗/工具技能供应商）
3. ✅ 外部 MCP 桥接工具被写作图调用 e2e（mcp_fake2_echo）
4. ✅ 项目级技能绑定: Project.skill_packs 列 + Alembic 0002 幂等迁移（含表/列守卫）+ setting/chapter 图自动读取 + 前端 SettingsView 技能开关
   - 关键修复: 列名 skills 与 M4 技能 relationship 重名触发懒加载 MissingGreenlet → 改名 skill_packs（含真实 DB 列修复 + 前端字段）
5. ✅ 全量回归: pytest 37 passed、npm build 成功、验收冒烟通过

- 提交后总计 38 项测试（parity2 + graphs3 + tools6 + knowledge5 + mcp3 + skills10 + api_integration8 + api_parity…）
