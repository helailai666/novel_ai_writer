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
