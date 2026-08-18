"""LLM 供应商测试 — OpenAI 兼容适配器的工具调用解析/回传（真实供应商路径）

覆盖 bug：langchain AIMessage.tool_calls 为 {name, args, id, type} dict，
旧代码按 OpenAI 原始 {function: {name, arguments}} 解析 → name/args 丢失；
且回传 assistant 工具调用时未转成 langchain 格式 → TypeError。
"""

from types import SimpleNamespace

from app.core.llm.providers.openai_compat import OpenAICompatProvider, _to_lc_messages
from app.core.llm.schemas import LLMMessage, ToolCall


def _fake_resp(content: str, tool_calls=None) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls or [], usage_metadata=None, response_metadata={})


def test_to_response_parses_langchain_tool_calls():
    """langchain AIMessage 风格 dict：{name, args, id, type}"""
    resp = _fake_resp(
        "",
        [
            {"id": "call_1", "name": "web_search", "args": {"query": "仙侠"}, "type": "tool_call"},
            {"id": "call_2", "name": "setting_query", "args": {"keyword": "剑"}, "type": "tool_call"},
        ],
    )
    out = OpenAICompatProvider._to_response(resp)
    assert [t.name for t in out.tool_calls] == ["web_search", "setting_query"]
    assert out.tool_calls[0].arguments == {"query": "仙侠"}
    assert out.tool_calls[0].id == "call_1"


def test_to_response_parses_openai_raw_dict():
    """OpenAI 原始风格 dict：{id, type: function, function: {name, arguments}}"""
    resp = _fake_resp(
        "",
        [{"id": "c9", "type": "function", "function": {"name": "hot_meme_lookup", "arguments": '{"phrase": "绝了"}'}}],
    )
    out = OpenAICompatProvider._to_response(resp)
    assert out.tool_calls[0].name == "hot_meme_lookup"
    assert out.tool_calls[0].arguments == {"phrase": "绝了"}
    assert out.tool_calls[0].id == "c9"


def test_to_response_skips_non_function_calls():
    resp = _fake_resp("纯文本", [{"id": "x", "type": "refusal", "refusal": "no"}])
    out = OpenAICompatProvider._to_response(resp)
    assert out.tool_calls == [] and out.content == "纯文本"


def test_to_lc_messages_assistant_tool_calls_roundtrip():
    """我们的 ToolCall → langchain AIMessage 格式（不再抛 unexpected keyword）"""
    msg = LLMMessage(
        role="assistant",
        content="",
        tool_calls=[
            ToolCall(id="c1", name="web_search", arguments={"query": "青龙"}).model_dump(),
            ToolCall(id="c2", name="setting_query", arguments={"keyword": "剑"}).model_dump(),
        ],
    )
    lc = _to_lc_messages([msg])
    assert len(lc) == 1
    calls = lc[0].tool_calls
    assert calls == [
        {"id": "c1", "name": "web_search", "args": {"query": "青龙"}, "type": "tool_call"},
        {"id": "c2", "name": "setting_query", "args": {"keyword": "剑"}, "type": "tool_call"},
    ]


def test_to_lc_messages_accepts_raw_dicts():
    """手写 dict（含 arguments 键）也应转换为 langchain 格式"""
    msg = LLMMessage(
        role="assistant", content="",
        tool_calls=[{"id": "c3", "name": "web_search", "arguments": {"query": "x"}}],
    )
    lc = _to_lc_messages([msg])
    assert lc[0].tool_calls[0]["name"] == "web_search" and lc[0].tool_calls[0]["args"] == {"query": "x"}
