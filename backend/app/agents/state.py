"""LangGraph 状态定义 — NovelState（可 checkpoint）

约定：
- events 字段用 Annotated[list, add] reducer：节点只返回自己新增的事件
- final_output 由收尾节点写入，供非流式调用读取
"""

from operator import add
from typing import Annotated, Any, Optional, TypedDict


class NovelState(TypedDict):
    # ── 输入 ────────────────────────────────────────────────────
    project_id: str
    task: str                                   # 用户任务描述
    model: Optional[str]                        # 供应商/模型覆盖（如 "deepseek:deepseek-chat"）
    llm_config: Optional[dict]                  # 项目级 LLM 配置字典（前台配置解析，含 api_key/api_base）
    graph: str                                  # 图名: setting / chapter / review

    # ── 业务输入（按图取用） ─────────────────────────────────────
    kind: Optional[str]                        # 设定类型: world/character/item/skill/faction/location/outline
    mode: Optional[str]                        # 章节模式: generate/continue/polish/rewrite
    name: Optional[str]                         # 设定名 / 角色名等
    category: Optional[str]                     # 类别
    role: Optional[str]                         # 角色定位
    extra: Optional[str]                        # 额外要求
    style: Optional[str]                        # 写作风格
    target_word_count: Optional[int]            # 目标字数
    prompt: Optional[str]                       # 章节生成提示词
    chapter_id: Optional[str]                   # 续写/润色目标章节
    chapter_number: Optional[int]               # 新建章节编号
    volume_id: Optional[str]                    # 所属卷
    content: Optional[str]                      # 待审核/待润色内容
    context: Optional[str]                      # 补充上下文
    dimensions: Optional[list[str]]             # 审核维度
    skills: Optional[list[str]]                 # 启用的技能包名（P6）
    history: Optional[list[dict]]               # 对话历史 [{"role","content"}]（L 轮多轮上下文）

    # ── 运行期状态 ──────────────────────────────────────────────
    settings_snapshot: dict[str, Any]           # 检索到的设定快照
    knowledge: list[dict]                       # 知识检索结果（P4 启用）
    sources: list[dict]                         # QA 图来源（doc/meme/web，K 轮）
    draft: Optional[str]                        # 草稿
    review: dict[str, Any]                      # 审核结果 {score, summary, issues, suggestions, dimension_scores}
    reviews: Annotated[list[dict], add]         # 审核图并行维度结果
    revision_round: int
    max_revisions: int
    review_threshold: int
    final_output: dict[str, Any]                # 最终输出 {content, is_mock, ...}
    events: Annotated[list[dict], add]          # GraphEvent 列表（SSE 回放）
    run_id: Optional[str]                       # agent_runs 主键
