"""Agent 基类 — LangChain 集成 + 多提供商 + Mock fallback"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── 配置 ──────────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    """Agent 通用配置"""
    llm_provider: str = "openai"       # openai / deepseek / ollama
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    api_base: Optional[str] = None     # None 则用 provider 默认
    temperature: float = 0.7
    max_tokens: int = 4096
    streaming: bool = False


# ── 默认 API 地址 ────────────────────────────────────────────────

_PROVIDER_DEFAULTS = {
    "openai":    {"api_base": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "deepseek":  {"api_base": "https://api.deepseek.com/v1", "env_key": "DEEPSEEK_API_KEY"},
    "ollama":    {"api_base": "http://localhost:11434/v1", "env_key": ""},
}


class AgentResult(BaseModel):
    """Agent 执行结果"""
    success: bool
    content: str = ""
    error: str = ""
    usage: dict = {}


# ── Prompt 模板管理 ──────────────────────────────────────────────

@dataclass
class PromptTemplate:
    """可复用的 Prompt 模板"""
    name: str
    system: str
    user_template: str = "{task}"

    def format(self, task: str, context: dict = None) -> tuple[str, str]:
        """返回 (system_message, user_message)"""
        ctx = context or {}
        user = self.user_template.format(task=task, **ctx)
        return self.system, user


# ── 内置模板 ─────────────────────────────────────────────────────

CREATIVE_SYSTEM = """You are a creative novelist and world-builder assistant.
You specialize in creating rich, consistent fictional worlds, characters, items, and settings for novels.
Always output structured, well-formatted content in Chinese by default.
Be imaginative but maintain internal consistency with any provided context."""

WRITER_SYSTEM = """You are a professional novelist specializing in long-form fiction.
Write engaging, well-paced chapter content with vivid descriptions, natural dialogue, and consistent characterization.
Follow the provided outline and context strictly. Output in Chinese by default.
Maintain the tone and style specified by the user."""

REVIEWER_SYSTEM = """You are a professional editor and literary critic.
Review the provided text for consistency, logic, pacing, prose quality, character development,
foreshadowing, and reader engagement. Provide detailed, actionable feedback.
Always output a structured review with scores, issues, suggestions, and highlights.
Respond in Chinese."""

SEARCH_SYSTEM = """You are a research assistant for novel writing.
Synthesize search results into useful references for the novelist.
Provide relevant facts, cultural details, historical context, or literary references
that can enrich the novel's world-building and plot development."""


# ── 基类 ─────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """Agent 基类：集成 LangChain + 多提供商 + 自动降级到 Mock

    使用方式
    --------
    agent = WriterAgent(llm_provider="deepseek", model="deepseek-chat")
    result = await agent.generate("写一章...")
    """

    # 子类覆盖
    default_system_prompt: str = "You are a helpful assistant for novel writing."
    default_model: str = "gpt-4o-mini"

    def __init__(self, config: AgentConfig = None, **kwargs):
        # 合并配置
        cfg_dict = {}
        if config:
            cfg_dict = config.model_dump()
        cfg_dict.update({k: v for k, v in kwargs.items() if v is not None})

        self.config = AgentConfig(**cfg_dict)

        # 自动补全 api_key / api_base
        self._resolve_config()

        # 初始化 LLM
        self._llm = None
        self._mock_mode = False
        self._init_llm()

    # ── 配置解析 ──────────────────────────────────────────────────

    def _resolve_config(self):
        """从环境变量自动补全配置"""
        provider = self.config.llm_provider
        defaults = _PROVIDER_DEFAULTS.get(provider, {})

        # API Key
        if not self.config.api_key and defaults.get("env_key"):
            self.config.api_key = os.getenv(defaults["env_key"], "")

        # API Base
        if not self.config.api_base:
            self.config.api_base = defaults.get("api_base", "https://api.openai.com/v1")

    def _init_llm(self):
        """初始化 LLM 实例"""
        if not self.config.api_key and self.config.llm_provider != "ollama":
            logger.warning(
                f"⚠️  No API key for '{self.config.llm_provider}', "
                f"falling back to mock mode"
            )
            self._mock_mode = True
            return

        try:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            logger.info(
                f"✅ LLM initialized: provider={self.config.llm_provider}, "
                f"model={self.config.model}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to init LLM: {e}")
            self._mock_mode = True

    @property
    def is_mock(self) -> bool:
        return self._mock_mode

    # ── 核心接口 ──────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        context: dict = None,
        system_prompt: str = None,
    ) -> AgentResult:
        """执行 Agent 任务（非流式）

        Args:
            task: 用户任务描述
            context: 上下文信息（设定、前文等）
            system_prompt: 自定义 system prompt（None 则用默认）
        """
        if self._mock_mode:
            return await self._mock_run(task, context)

        system = system_prompt or self.default_system_prompt
        user = self._build_user_message(task, context or {})

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            messages = [SystemMessage(content=system), HumanMessage(content=user)]
            response = await self._llm.ainvoke(messages)

            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = dict(response.usage_metadata)
            elif hasattr(response, "response_metadata"):
                usage = dict(response.response_metadata.get("token_usage", {}))

            return AgentResult(
                success=True,
                content=str(response.content),
                usage=usage,
            )
        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}")
            return AgentResult(success=False, content="", error=str(e))

    async def run_stream(
        self,
        task: str,
        context: dict = None,
        system_prompt: str = None,
    ) -> AsyncIterator[str]:
        """执行 Agent 任务（流式），逐块返回内容

        Yields:
            str: 每个 token 块
        """
        if self._mock_mode:
            async for chunk in self._mock_stream(task, context):
                yield chunk
            return

        system = system_prompt or self.default_system_prompt
        user = self._build_user_message(task, context or {})

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            messages = [SystemMessage(content=system), HumanMessage(content=user)]
            async for chunk in self._llm.astream(messages):
                if chunk.content:
                    yield str(chunk.content)
        except Exception as e:
            logger.error(f"❌ LLM stream failed: {e}")
            yield f"\n\n[生成中断: {e}]"

    @abstractmethod
    async def generate(self, prompt: str, context: dict = None) -> AgentResult:
        """子类实现：生成内容"""
        ...

    async def review(self, content: str, criteria: str = "") -> AgentResult:
        """审核/评估内容（默认实现，子类可覆盖）"""
        task = f"请审核以下内容:\n\n{content}"
        if criteria:
            task += f"\n\n审核维度: {criteria}"
        return await self.run(task)

    # ── 内部方法 ──────────────────────────────────────────────────

    def _build_user_message(self, task: str, context: dict) -> str:
        """构建用户消息"""
        parts = []
        if context:
            parts.append(f"【上下文信息】\n{json.dumps(context, ensure_ascii=False, indent=2)}")
        parts.append(f"【任务】\n{task}")
        return "\n\n".join(parts)

    async def _mock_run(self, task: str, context: dict = None) -> AgentResult:
        """Mock 模式 — 返回占位内容"""
        content = self._generate_mock(task, context)
        return AgentResult(success=True, content=content, usage={"mock": True})

    async def _mock_stream(self, task: str, context: dict = None) -> AsyncIterator[str]:
        """Mock 模式流式 — 逐词输出"""
        import asyncio
        content = self._generate_mock(task, context)
        for word in content:
            yield word
            await asyncio.sleep(0.02)

    def _generate_mock(self, task: str, context: dict = None) -> str:
        """生成 mock 内容（子类可覆盖）"""
        return (
            f"[Mock 生成 — 未配置 LLM API Key]\n\n"
            f"任务: {task[:200]}\n\n"
            f"请设置环境变量 OPENAI_API_KEY / DEEPSEEK_API_KEY 以启用真实 AI 生成。\n"
            f"或设置 LLM_PROVIDER=ollama 使用本地模型。\n\n"
            f"支持的提供商: openai / deepseek / ollama"
        )

    def _build_system_prompt(self, role: str, extra: str = "") -> str:
        """构建系统提示词（向后兼容）"""
        prompt = f"You are a {role} for novel writing."
        if extra:
            prompt += f"\n{extra}"
        return prompt
