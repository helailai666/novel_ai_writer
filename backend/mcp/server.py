"""
NovelAI Writer MCP Server — 通过 MCP 协议控制小说创作全流程

本服务遵循 Model Context Protocol 标准，提供以下工具：
- 项目管理: create/list/delete project
- 设定管理: generate/edit 12大创作模块
- 创作控制: generate chapter/batch generate
- 进度查询: progress report/statistics
- 搜索参考: search novel reference

启动方式:
    python -m novel_ai_writer.backend.mcp.server

注册到 AstrBot MCP:
    {
        "mcpServers": {
            "novel-writer": {
                "command": "python",
                "args": ["-m", "novel_ai_writer.backend.mcp.server"],
                "cwd": "D:\\project\\novel_ai_writer"
            }
        }
    }
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# ─── MCP SDK 导入 ──────────────────────────────────
try:
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# ─── 日志配置 ──────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("novel-writer-mcp")

# ─── 项目路径 ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # novel_ai_writer/
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class NovelWriterMCPServer:
    """NovelAI Writer MCP Server"""

    def __init__(self):
        self.server = Server("novel-writer")
        self._projects: dict[str, dict] = {}  # 内存存储（后续替换为数据库）
        self._setup_handlers()

    # ─── 工具定义 ──────────────────────────────────

    def _setup_handlers(self):
        """注册 MCP 工具处理器"""

        @self.server.list_tools()
        async def handle_list_tools():
            """列出所有可用的创作工具"""
            return [
                # === 项目管理 ===
                types.Tool(
                    name="create_project",
                    description="创建新的小说项目",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "小说标题"},
                            "genre": {
                                "type": "string",
                                "description": "小说类型: 玄幻/言情/科幻/悬疑/都市/历史/武侠/轻小说",
                                "enum": ["玄幻", "言情", "科幻", "悬疑", "都市", "历史", "武侠", "轻小说", "其他"],
                            },
                            "style": {
                                "type": "string",
                                "description": "风格: 爽文/慢热/甜宠/热血/悬疑",
                                "enum": ["爽文", "慢热", "甜宠", "热血", "悬疑", "文艺"],
                            },
                        },
                        "required": ["title", "genre"],
                    },
                ),
                types.Tool(
                    name="list_projects",
                    description="列出所有小说项目及进度",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                types.Tool(
                    name="get_project_progress",
                    description="查询指定项目的创作进度",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                        },
                        "required": ["project_id"],
                    },
                ),
                # === 设定生成 ===
                types.Tool(
                    name="generate_world_setting",
                    description="生成世界观设定",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "era": {"type": "string", "description": "时代背景"},
                            "rules": {"type": "string", "description": "世界规则/力量体系"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="generate_characters",
                    description="生成角色设定（主角/配角/反派）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "protagonist_name": {"type": "string", "description": "主角名称（可选）"},
                            "character_count": {
                                "type": "integer",
                                "description": "生成角色数量（含主角）",
                                "default": 5,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="generate_items",
                    description="生成道具体系",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="generate_outline",
                    description="生成小说大纲（分卷+章节）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "total_chapters": {
                                "type": "integer",
                                "description": "总章节数",
                                "default": 100,
                            },
                            "volumes": {
                                "type": "integer",
                                "description": "分卷数",
                                "default": 5,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                # === 创作控制 ===
                types.Tool(
                    name="generate_chapter",
                    description="生成指定章节内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "chapter_number": {
                                "type": "integer",
                                "description": "章节编号",
                            },
                            "chapter_title": {
                                "type": "string",
                                "description": "章节标题（可选，留空自动生成）",
                            },
                            "word_count": {
                                "type": "integer",
                                "description": "目标字数",
                                "default": 2000,
                            },
                        },
                        "required": ["project_id", "chapter_number"],
                    },
                ),
                types.Tool(
                    name="batch_generate_chapters",
                    description="批量生成连续章节",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "start_chapter": {
                                "type": "integer",
                                "description": "起始章节",
                            },
                            "end_chapter": {
                                "type": "integer",
                                "description": "结束章节",
                            },
                        },
                        "required": ["project_id", "start_chapter", "end_chapter"],
                    },
                ),
                # === 搜索参考 ===
                types.Tool(
                    name="search_novel_reference",
                    description="搜索小说参考，自动分析设定",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "novel_name": {
                                "type": "string",
                                "description": "要参考的小说名称",
                            },
                            "project_id": {
                                "type": "string",
                                "description": "（可选）自动填充到指定项目",
                            },
                        },
                        "required": ["novel_name"],
                    },
                ),
                # === 进度与统计 ===
                types.Tool(
                    name="get_statistics",
                    description="获取创作统计数据",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                        },
                        "required": ["project_id"],
                    },
                ),
                # === 审核系统（Revise Agent） ===
                types.Tool(
                    name="review_chapter",
                    description="审核单章内容：设定一致性/语法/不通顺/文笔评分",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "chapter_number": {"type": "integer", "description": "章节编号"},
                            "review_depth": {
                                "type": "string",
                                "description": "审核深度",
                                "default": "standard",
                            },
                        },
                        "required": ["project_id", "chapter_number"],
                    },
                ),
                types.Tool(
                    name="review_batch_chapters",
                    description="批量审核多章内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "start_chapter": {"type": "integer", "description": "起始章节"},
                            "end_chapter": {"type": "integer", "description": "结束章节"},
                        },
                        "required": ["project_id", "start_chapter", "end_chapter"],
                    },
                ),
                types.Tool(
                    name="review_setting_consistency",
                    description="检查章节内容与所有设定的匹配度",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "scope": {"type": "string", "description": "检查范围: all/recent", "default": "all"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="review_continuity",
                    description="检查章节间的连贯性（剧情衔接/时间线/角色状态）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "chapter_range": {"type": "string", "description": "范围", "default": "全部"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="review_grammar",
                    description="语法和通顺度检查（错别字/病句/标点）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "chapter_number": {"type": "integer", "description": "章节编号"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="review_foreshadowing",
                    description="伏笔回收追踪检查",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="review_pacing",
                    description="剧情节奏分析（爽点密度/冲突频率/高潮间隔）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "volume": {"type": "integer", "description": "卷号"},
                        },
                        "required": ["project_id"],
                    },
                ),
                types.Tool(
                    name="generate_review_report",
                    description="生成完整项目审校报告",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "项目ID"},
                            "format": {"type": "string", "description": "格式: summary/detailed/score", "default": "summary"},
                        },
                        "required": ["project_id"],
                    },
                ),
            ]

        # ─── 工具调用处理器 ──────────────────────

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None):
            """处理 MCP 工具调用"""
            args = arguments or {}

            if name == "create_project":
                return self._mock_result(f"✅ 项目《{args['title']}》({args['genre']}) 创建成功！项目ID: proj_{len(self._projects)+1:04d}")

            elif name == "list_projects":
                if not self._projects:
                    return self._mock_result("📋 当前无小说项目。使用 create_project 创建新项目。")
                lines = ["📋 小说项目列表:\n"]
                for pid, proj in self._projects.items():
                    lines.append(f"- {proj['title']} [{proj['genre']}] 进度: {proj.get('progress', '0%')}")
                return self._mock_result("\n".join(lines))

            elif name == "get_project_progress":
                pid = args["project_id"]
                return self._mock_result(
                    f"📊 项目 {pid} 进度报告:\n"
                    f"- 设定完成度: 60%\n"
                    f"- 大纲完成度: 100%\n"
                    f"- 章节完成度: 12/100 (12%)\n"
                    f"- 总字数: 24,000 字\n"
                    f"- 当前阶段: 章节写作中"
                )

            elif name == "generate_world_setting":
                return self._mock_result("🌍 世界观设定已生成:\n- 时代: 架空修仙世界\n- 地理: 五洲大陆\n- 力量体系: 灵气修炼体系（练气→筑基→金丹→元婴→化神）\n- 种族: 人族/妖族/魔族")

            elif name == "generate_characters":
                return self._mock_result(
                    "👤 角色设定已生成:\n"
                    "1. 主角: 林玄 (平凡少年, 天赋异禀)\n"
                    "2. 女主: 苏婉儿 (宗门圣女, 温婉坚韧)\n"
                    "3. 导师: 云游老人 (神秘高人)\n"
                    "4. 挚友: 王小虎 (憨厚忠诚)\n"
                    "5. 反派: 暗影魔尊 (终极BOSS)"
                )

            elif name == "generate_items":
                return self._mock_result(
                    "🗡️ 道具体系已生成:\n"
                    "- 神器: 九天玄剑 (传说级)\n"
                    "- 防具: 玄天战甲 (史诗级)\n"
                    "- 丹药: 九转金丹, 筑基丹\n"
                    "- 法宝: 乾坤袋, 传送符"
                )

            elif name == "generate_outline":
                total = args.get("total_chapters", 100)
                vols = args.get("volumes", 5)
                return self._mock_result(
                    f"📖 大纲已生成 ({vols}卷/{total}章):\n"
                    f"第一卷「初入仙途」(1-20章): 主角入门, 拜师学艺\n"
                    f"第二卷「宗门风云」(21-40章): 宗门大比, 崭露头角\n"
                    f"第三卷「秘境探险」(41-60章): 秘境寻宝, 实力突破\n"
                    f"第四卷「天下争霸」(61-80章): 正邪大战, 声名鹊起\n"
                    f"第五卷「登临巅峰」(81-100章): 飞升成仙, 终章"
                )

            elif name == "generate_chapter":
                ch = args["chapter_number"]
                title = args.get("chapter_title", f"第{ch}章")
                return self._mock_result(
                    f"✅ 第{ch}章「{title}」已生成 ({args.get('word_count', 2000)}字)\n"
                    f"[内容摘要]: 林玄在宗门广场集合, 今日是入门考核的日子..."
                )

            elif name == "batch_generate_chapters":
                start = args["start_chapter"]
                end = args["end_chapter"]
                return self._mock_result(f"✅ 第{start}-{end}章批处理完成！共{end-start+1}章，约{(end-start+1)*2000}字")

            elif name == "search_novel_reference":
                novel = args["novel_name"]
                return self._mock_result(
                    f"🔍 已搜索《{novel}》的分析结果:\n"
                    f"[此功能需集成 Search Agent + Tavily 后生效]\n"
                    f"预计输出: 类型/世界观/角色体系/能力体系/大纲结构"
                )

            elif name == "get_statistics":
                return self._mock_result(
                    "📊 数据统计:\n"
                    "- 总字数: 24,000\n"
                    "- 总章节: 12\n"
                    "- 角色数: 5\n"
                    "- 道具数: 8\n"
                    "- 设定模块完成: 3/12"
                )

            # ─── 审核工具处理器 ──────────────────────
            elif name == "review_chapter":
                ch = args["chapter_number"]
                depth = args.get("review_depth", "standard")
                return self._mock_result(
                    f"🔍 第{ch}章审核报告 (审核深度: {depth}):\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📊 综合评分: 82/100\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ 设定一致性: 通过\n"
                    "   - 角色行为符合设定 ✅\n"
                    "   - 能力等级符合世界观 ✅\n"
                    "   - 道具使用符合设定 ✅\n\n"
                    "⚠️ 语法与表达: 1处问题\n"
                    "   - 第3段: '他一脚踩碎了地面' → 建议改为'他一脚重重跺下,地面龟裂'（原句略显平淡）\n\n"
                    "✅ 语句通顺度: 整体流畅\n\n"
                    "📝 文笔评分: B+\n"
                    "   - 描写: 7/10 可增加环境细节\n"
                    "   - 对话: 8/10 自然\n"
                    "   - 节奏: 8/10 紧凑\n\n"
                    "💡 修改建议: 第3段描写可更生动, 建议增加环境烘托"
                )

            elif name == "review_batch_chapters":
                start = args["start_chapter"]
                end = args["end_chapter"]
                return self._mock_result(
                    f"🔍 第{start}-{end}章批量审核完成:\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 综合评分: 78/100\n\n"
                    f"✅ 第{start}-{start+4}章: 质量较好 (85分)\n"
                    f"⚠️ 第{start+5}-{end-3}章: 部分章节对话偏多, 建议增加动作描写 (76分)\n"
                    f"❌ 第{end-2}-{end}章: 结尾三章节奏偏慢, 建议适当删减 (72分)\n\n"
                    f"📝 整体建议: 第{start+5}-{end}章建议优化节奏, 增加冲突密度"
                )

            elif name == "review_setting_consistency":
                scope = args.get("scope", "all")
                return self._mock_result(
                    "🔍 设定一致性检查报告:\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ 角色能力与设定一致: 5/5 角色\n"
                    "✅ 道具等级与描述一致: 8/8 物品\n"
                    "⚠️ 世界观设定匹配: 发现2处偏差\n"
                    "   - 第8章: 描写'灵气稀薄'但前文设定为'灵气浓郁期' ⚠️\n"
                    "   - 第12章: 主角使用金丹期能力, 但当前境界为筑基期 ❌\n\n"
                    "📌 建议: 修复第8章和第12章的设定偏差"
                )

            elif name == "review_continuity":
                return self._mock_result(
                    "🔍 连贯性检查报告:\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ 剧情衔接: 12/12 章衔接自然\n"
                    "⚠️ 时间线: 第5章出现时间跳跃未说明\n"
                    "✅ 角色状态: 保持连贯\n\n"
                    "💡 建议: 第5章开头增加时间标注, 如'三日后...'"
                )

            elif name == "review_grammar":
                ch = args.get("chapter_number", 0)
                target = f"第{ch}章" if ch else "全部章节"
                return self._mock_result(
                    f"🔍 语法检查报告 ({target}):\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ 错别字: 0处\n"
                    "⚠️ 病句: 1处\n"
                    "   - '他不仅修炼速度快, 而且还很聪明' → 建议删去冗余关联词\n"
                    "✅ 标点符号: 全部正确\n"
                    "✅ 分段: 合理\n\n"
                    "📝 语感评分: 86/100 (通顺流畅)"
                )

            elif name == "review_foreshadowing":
                return self._mock_result(
                    "🔍 伏笔回收追踪报告:\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 已设置伏笔: 8个\n"
                    "✅ 已回收: 5个\n"
                    "⏳ 未回收: 3个\n"
                    "   - 伏笔A: '神秘玉佩的来历' (第1章设置, 预计第30章回收)\n"
                    "   - 伏笔B: '师尊的真实身份' (第5章设置, 预计第45章回收)\n"
                    "   - 伏笔C: '古墓中的秘密' (第10章设置, 预计第50章回收)\n\n"
                    "📝 建议: 伏笔C可在近几章安排回收线索"
                )

            elif name == "review_pacing":
                vol = args.get("volume", 0)
                target = f"第{vol}卷" if vol else "全书"
                return self._mock_result(
                    f"🔍 节奏分析报告 ({target}):\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📊 爽点密度: 每3章1个 (合理范围: 每2-4章)\n"
                    "📊 冲突频率: 每2章1次 (良好)\n"
                    "📊 高潮间隔: 每10章1次 (建议每8-12章)\n\n"
                    "📈 节奏曲线: 整体呈上升趋势, 良好\n"
                    "⚠️ 第8-10章: 连续3章无冲突, 建议穿插小高潮\n\n"
                    "💡 建议: 在第9章增加一个小冲突或悬念"
                )

            elif name == "generate_review_report":
                fmt = args.get("format", "summary")
                if fmt == "score":
                    return self._mock_result(
                        "📋 项目评分卡\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "📊 各维度评分:\n"
                        "   设定完整性: ████████░░ 80/100\n"
                        "   设定一致性: ███████░░░ 75/100\n"
                        "   文笔质量:   ████████░░ 82/100\n"
                        "   剧情连贯性: █████████░ 88/100\n"
                        "   节奏把控:   ████████░░ 78/100\n"
                        "   语法准确率: █████████░ 90/100\n"
                        "   伏笔管理:   ██████░░░░ 62/100\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "🏆 综合评分: 79/100 (B+)\n"
                        "💡 优先改进: 伏笔管理 + 设定一致性"
                    )
                else:
                    return self._mock_result(
                        "📋 项目审校报告 (摘要)\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"项目: {args.get('project_id')}\n"
                        "检查时间: 2026-06-02\n\n"
                        "🔍 本次检查覆盖: 6个维度\n\n"
                        "✅ 语法检查: 1处小问题\n"
                        "✅ 设定一致性: 2处偏差需修复\n"
                        "✅ 连贯性: 通过\n"
                        "✅ 伏笔追踪: 3个未回收\n"
                        "✅ 节奏分析: 建议优化第8-10章\n\n"
                        "📊 综合评分: 79/100 (B+)\n"
                        "📌 建议优先处理: 设定一致性偏差"
                    )

            else:
                raise ValueError(f"未知工具: {name}")

    def _mock_result(self, text: str):
        """生成工具调用结果"""
        return [types.TextContent(type="text", text=text)]

    # ─── 启动 ──────────────────────────────────────

    async def run(self):
        """启动 MCP Server"""
        if not MCP_AVAILABLE:
            print("MCP SDK is required. Install with: pip install mcp", file=sys.stderr)
            sys.exit(1)

        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="novel-writer",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


async def main():
    server = NovelWriterMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
