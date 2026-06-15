import json

import pytest
import requests

from API.providers import _anthropic_compatible, _gemini_compatible, _retry, anthropic, google


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]


# --- Anthropic conversion -------------------------------------------------


def test_anthropic_convert_messages_splits_system_and_handles_tool_round_trip():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "hi"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "search results"},
    ]

    system, converted = _anthropic_compatible._convert_messages(messages)

    assert system == "system prompt"
    assert converted[0] == {"role": "user", "content": "hi"}
    assert converted[1]["role"] == "assistant"
    assert converted[1]["content"][0] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "web_search",
        "input": {"query": "hi"},
    }
    assert converted[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "search results"}],
    }


def test_anthropic_convert_tools():
    converted = _anthropic_compatible._convert_tools(TOOLS)
    assert converted == [
        {
            "name": "web_search",
            "description": "Search the web.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]
    assert _anthropic_compatible._convert_tools(None) is None


def test_anthropic_convert_response_text_only():
    data = {"content": [{"type": "text", "text": "hello"}]}
    message = _anthropic_compatible._convert_response(data)
    assert message == {"role": "assistant", "content": "hello"}


def test_anthropic_convert_response_with_tool_use():
    data = {
        "content": [
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "toolu_1", "name": "web_search", "input": {"query": "news"}},
        ]
    }
    message = _anthropic_compatible._convert_response(data)

    assert message["content"] == "Let me check."
    assert message["tool_calls"] == [
        {
            "id": "toolu_1",
            "type": "function",
            "function": {"name": "web_search", "arguments": json.dumps({"query": "news"})},
        }
    ]


def test_anthropic_call_builds_request(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse({"content": [{"type": "text", "text": "hi there"}]})

    monkeypatch.setattr(_retry.requests, "post", fake_post)

    messages = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "hello"},
    ]
    result = anthropic.call(messages, tools=TOOLS, model="claude-x", temperature=0.5)

    assert result == {"role": "assistant", "content": "hi there"}
    assert captured["url"] == anthropic.ANTHROPIC_URL
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"]
    assert captured["json"]["model"] == "claude-x"
    assert captured["json"]["system"] == "sys prompt"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["json"]["temperature"] == 0.5
    assert captured["json"]["max_tokens"]
    assert captured["json"]["tools"][0]["name"] == "web_search"


# --- Gemini conversion ------------------------------------------------------


def test_gemini_convert_messages_handles_tool_round_trip():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "hi"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "search results"},
    ]

    system_instruction, contents = _gemini_compatible._convert_messages(messages)

    assert system_instruction == {"parts": [{"text": "system prompt"}]}
    assert contents[0] == {"role": "user", "parts": [{"text": "hi"}]}
    assert contents[1] == {
        "role": "model",
        "parts": [{"functionCall": {"name": "web_search", "args": {"query": "hi"}}}],
    }
    assert contents[2] == {
        "role": "user",
        "parts": [{"functionResponse": {"name": "web_search", "response": {"content": "search results"}}}],
    }


def test_gemini_convert_tools():
    converted = _gemini_compatible._convert_tools(TOOLS)
    assert converted == [
        {
            "functionDeclarations": [
                {
                    "name": "web_search",
                    "description": "Search the web.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ]
        }
    ]
    assert _gemini_compatible._convert_tools(None) is None


def test_gemini_convert_response_text_only():
    data = {"candidates": [{"content": {"role": "model", "parts": [{"text": "hello"}]}}]}
    message = _gemini_compatible._convert_response(data)
    assert message == {"role": "assistant", "content": "hello"}


def test_gemini_convert_response_with_function_call():
    data = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"functionCall": {"name": "web_search", "args": {"query": "news"}}}],
                }
            }
        ]
    }
    message = _gemini_compatible._convert_response(data)

    assert message["content"] is None
    assert len(message["tool_calls"]) == 1
    tool_call = message["tool_calls"][0]
    assert tool_call["function"]["name"] == "web_search"
    assert json.loads(tool_call["function"]["arguments"]) == {"query": "news"}
    assert tool_call["id"].startswith("call_")


def test_google_call_builds_request(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse({"candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}]})

    monkeypatch.setattr(_retry.requests, "post", fake_post)

    messages = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "hello"},
    ]
    result = google.call(messages, tools=TOOLS, model="gemini-x", temperature=0.5, max_tokens=100)

    assert result == {"role": "assistant", "content": "hi"}
    assert "gemini-x" in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["json"]["system_instruction"] == {"parts": [{"text": "sys prompt"}]}
    assert captured["json"]["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert captured["json"]["generationConfig"] == {"temperature": 0.5, "maxOutputTokens": 100}
    assert captured["json"]["tools"][0]["functionDeclarations"][0]["name"] == "web_search"
