"""配置模型 — 全局配置（pydantic-settings，从 .env / 环境变量加载）

约定：环境变量全部扁平命名（见 .env.example），加载后在后置钩子中
组装成分组对象（llm / search / embedding / vector_store / mcp / skills / agent）。
"""

from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── 分组配置（程序化覆盖用；环境变量不直接映射到嵌套字段）──────────

class LLMSettings(BaseModel):
    """LLM 供应商配置"""

    provider: str = Field(default="openai", description="openai/deepseek/ollama/azure/anthropic/gemini/qwen/glm/kimi/mock")
    model: str = Field(default="gpt-4o-mini")
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    streaming: bool = False
    timeout: float = 60.0


class SearchSettings(BaseModel):
    """网络搜索配置"""

    provider: str = Field(default="auto", description="auto/tavily/duckduckgo/bing/searxng/bocha/mock")
    tavily_api_key: Optional[str] = None
    bing_api_key: Optional[str] = None
    bocha_api_key: Optional[str] = None
    searxng_url: Optional[str] = None
    cache_ttl: int = 3600
    max_cache_entries: int = 200


class EmbeddingSettings(BaseModel):
    """向量化嵌入配置"""

    provider: str = Field(default="mock", description="openai/local/mock")
    model: str = "text-embedding-3-small"
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class VectorStoreSettings(BaseModel):
    """向量存储配置"""

    backend: str = Field(default="chroma", description="chroma/faiss/mock")
    persist_dir: str = "./data/vectorstore"


class MCPSettings(BaseModel):
    """MCP 配置（服务端暴露 + 外部客户端接入）"""

    enabled: bool = True
    servers_file: str = "config/mcp_servers.yaml"
    server_name: str = "novel-writer"
    server_version: str = "0.2.0"


class SkillSettings(BaseModel):
    """Skills 技能包配置"""

    dirs: list[str] = Field(default_factory=lambda: ["skills"])
    auto_apply: bool = False


class AgentSettings(BaseModel):
    """Agent 编排配置"""

    max_revisions: int = 2          # 章节写作图：最大修订轮数
    review_threshold: int = 75      # 低于该分触发 rewrite
    streaming: bool = True
    persist_runs: bool = True       # 是否写入 agent_runs 表
    llm_supervisor: bool = True     # chat 图意图分类：True=LLM 优先（失败回退关键词）
    llm_supervisor_cache: bool = True   # 意图分类结果缓存（相同任务免重复 LLM 调用）
    llm_supervisor_cache_ttl: int = 300 # 分类缓存秒数
    knowledge_cache: bool = True        # 知识检索结果缓存（同查询免重复混合检索）
    knowledge_cache_ttl: int = 300      # 检索缓存秒数


# ── 顶层 Settings（扁平环境变量） ──────────────────────────────────

class Settings(BaseSettings):
    """应用配置，自动读取 .env 和环境变量"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 服务 ──────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 18000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── 数据库 ────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_ai_writer.db"

    # ── LLM 供应商 ────────────────────────────────────────────────
    LLM_PROVIDER: str = "openai"        # openai/deepseek/ollama/azure/anthropic/gemini/qwen/glm/kimi/mock
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: Optional[str] = None
    LLM_API_BASE: Optional[str] = "https://api.deepseek.com"

    # ── 各供应商 Key（供 factory 读取，均为可选）───────────────────
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DASHSCOPE_API_KEY: Optional[str] = None
    ZHIPU_API_KEY: Optional[str] = None
    MOONSHOT_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: Optional[str] = "2024-02-01"

    # ── 网络搜索 ──────────────────────────────────────────────────
    SEARCH_PROVIDER: str = "auto"       # auto/tavily/duckduckgo/bing/searxng/bocha/mock
    TAVILY_API_KEY: Optional[str] = None
    BING_API_KEY: Optional[str] = None
    BOCHA_API_KEY: Optional[str] = None
    SEARXNG_URL: Optional[str] = None
    SEARCH_CACHE_TTL: int = 3600

    # ── 向量化 / 向量存储 ─────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "mock"    # openai/local/mock
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_API_BASE: Optional[str] = None
    VECTOR_STORE_BACKEND: str = "chroma"  # chroma/faiss/mock
    VECTOR_STORE_PERSIST_DIR: str = "./data/vectorstore"

    # ── Agent 编排 ────────────────────────────────────────────────
    AGENT_MAX_REVISIONS: int = 2
    AGENT_REVIEW_THRESHOLD: int = 75
    AGENT_STREAMING: bool = True
    AGENT_PERSIST_RUNS: bool = True
    AGENT_LLM_SUPERVISOR: bool = True
    AGENT_LLM_SUPERVISOR_CACHE: bool = True
    AGENT_LLM_SUPERVISOR_CACHE_TTL: int = 300

    # ── 知识检索缓存 ──────────────────────────────────────────────
    KNOWLEDGE_CACHE_ENABLED: bool = True
    KNOWLEDGE_CACHE_TTL: int = 300

    # ── MCP ───────────────────────────────────────────────────────
    MCP_ENABLED: bool = True
    MCP_SERVERS_FILE: str = "config/mcp_servers.yaml"

    # ── Skills ────────────────────────────────────────────────────
    SKILLS_DIRS: str = "skills"         # 逗号分隔目录列表

    # ── 分组对象（由扁平字段组装，供代码直接使用）──────────────────
    llm: LLMSettings = LLMSettings()
    search: SearchSettings = SearchSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    mcp: MCPSettings = MCPSettings()
    skills: SkillSettings = SkillSettings()
    agent: AgentSettings = AgentSettings()

    def model_post_init(self, __context) -> None:
        """用扁平字段组装分组对象（并兼容 DEBUG 级别）"""
        self.llm = LLMSettings(
            provider=self.LLM_PROVIDER,
            model=self.LLM_MODEL,
            api_key=self.LLM_API_KEY,
            api_base=self.LLM_API_BASE or None,
        )
        self.search = SearchSettings(
            provider=self.SEARCH_PROVIDER,
            tavily_api_key=self.TAVILY_API_KEY,
            bing_api_key=self.BING_API_KEY,
            bocha_api_key=self.BOCHA_API_KEY,
            searxng_url=self.SEARXNG_URL,
            cache_ttl=self.SEARCH_CACHE_TTL,
        )
        self.embedding = EmbeddingSettings(
            provider=self.EMBEDDING_PROVIDER,
            model=self.EMBEDDING_MODEL,
            api_key=self.EMBEDDING_API_KEY,
            api_base=self.EMBEDDING_API_BASE,
        )
        self.vector_store = VectorStoreSettings(
            backend=self.VECTOR_STORE_BACKEND,
            persist_dir=self.VECTOR_STORE_PERSIST_DIR,
        )
        self.mcp = MCPSettings(
            enabled=self.MCP_ENABLED,
            servers_file=self.MCP_SERVERS_FILE,
        )
        self.skills = SkillSettings(
            dirs=[d.strip() for d in self.SKILLS_DIRS.split(",") if d.strip()],
        )
        self.agent = AgentSettings(
            max_revisions=self.AGENT_MAX_REVISIONS,
            review_threshold=self.AGENT_REVIEW_THRESHOLD,
            streaming=self.AGENT_STREAMING,
            persist_runs=self.AGENT_PERSIST_RUNS,
            llm_supervisor=self.AGENT_LLM_SUPERVISOR,
            llm_supervisor_cache=self.AGENT_LLM_SUPERVISOR_CACHE,
            llm_supervisor_cache_ttl=self.AGENT_LLM_SUPERVISOR_CACHE_TTL,
            knowledge_cache=self.KNOWLEDGE_CACHE_ENABLED,
            knowledge_cache_ttl=self.KNOWLEDGE_CACHE_TTL,
        )
        if self.DEBUG:
            self.LOG_LEVEL = "DEBUG"


settings = Settings()
