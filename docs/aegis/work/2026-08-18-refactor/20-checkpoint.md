# TodoCheckpointDraft — 2026-08-18 首检

## 当前 todo / 活动切片

- 当前切片: P0 环境与依赖（venv 重建、依赖安装、配置分层、logging）
- 已完成 todos: 无（P0 in_progress）
- 下一步: 等 pip 安装完成 → 验证 app 启动 /health 200

## 证据引用（EvidenceRefs）

- TaskStartSnapshot: HEAD e9af586d57b571dcbba1f967a8065c912734f96e，branch main，工作区干净，upstream 0/0
- venv 重建: .venv = Python 3.13.13（`python3 -m venv .venv` 成功）
- requirements.txt 已升级（langgraph>=1.0, mcp>=1.0, chromadb>=0.6, alembic, langchain-*>=1.0）
- app/config.py → app/config/ 包（settings.py 扩展分组配置 + logging.py + mcp_servers.example.yaml），旧文件已删
- .env.example 已扩展全量配置

## 阻塞项

- 后台 job bash-1: pip install -r backend/requirements.txt（运行中）
- Hindsight 服务 401 未认证（环境问题，改用 docs/aegis 记录）

## 漂移检查（DriftCheckDraft）

- 范围: 未越界（仅 P0 配置/环境，未动业务代码）
- 兼容: config 包保持 `from app.config import settings` 兼容
- 决策: continue

## 恢复提示（ResumeStateHint）

- 恢复点: P0 剩余 = 等依赖装完 → 启动验证 → 提交 P0
