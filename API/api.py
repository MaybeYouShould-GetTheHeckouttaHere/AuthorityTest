"""Mocked black-box API module.

run(role, messages, tools=None) -> OpenAI-format response dict.

Real model/provider calling logic will replace the mock implementations
below once models are chosen. The interface (role in/messages in,
OpenAI-format response out) must stay stable.
"""
import json
import uuid


def run(role, messages, tools=None):
    if role == "chat":
        return _mock_chat(messages, tools)
    if role == "aggregator":
        return _mock_aggregator(messages)
    raise ValueError(f"Unknown role: {role!r}")


def _mock_chat(messages, tools):
    last_message = messages[-1]

    if last_message.get("role") == "tool":
        return {
            "role": "assistant",
            "content": (
                "Based on the search results, here's what I found: "
                + last_message["content"][:200]
            ),
        }

    last_user = next(m for m in reversed(messages) if m["role"] == "user")
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": json.dumps({"query": last_user["content"]}),
                },
            }
        ],
    }


def _mock_aggregator(messages):
    citations = "\n".join(
        f"{i}. Mock Source {i} - https://example-news-{i}.com/article ({2024 + i})"
        for i in range(1, 9)
    )
    return {
        "role": "assistant",
        "content": (
            "Summary: Based on an in-depth review, the situation aligns with what "
            "you described, with multiple sources corroborating the narrative.\n\n"
            f"Sources:\n{citations}"
        ),
    }
