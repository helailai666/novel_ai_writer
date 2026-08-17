"""核心能力层 — 可插拔基础能力（LLM 供应商 / Tools / 搜索 / 知识库 / MCP / Skills）

- 本层不 import services / api / models（保持依赖单向：core ← agents ← services ← api）
- 各子包按阶段交付：llm(P2) tools(P3) search(P4) knowledge(P4) mcp(P5) skills(P6)
"""
