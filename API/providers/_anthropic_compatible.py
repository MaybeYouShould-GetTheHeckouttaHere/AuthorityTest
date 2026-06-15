"""Shared call logic for Anthropic Messages API-compatible endpoints.

Used by providers whose API follows Anthropic's `/v1/messages` schema
(Anthropic itself, Z.AI's Anthropic-compatible endpoint, etc). Converts
between OpenAI-format messages/tools/responses and Anthropic's format.

https://docs.anthropic.com/en/api/messages
"""
import json
import os

from API.providers._retry import MAX_RETRIES, post_with_retry

DEFAULT_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


def _convert_messages(messages):
    """OpenAI-format messages -> (system_prompt, Anthropic-format messages)."""
    system_parts = []
    converted = []

    for message in messages:
        role = message["role"]

        if role == "system":
            system_parts.append(message["content"])
            continue

        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message["content"],
                        }
                    ],
                }
            )
            continue

        if role == "assistant" and message.get("tool_calls"):
            content = []
            if message.get("content"):
                content.append({"type": "text", "text": message["content"]})
            for tool_call in message["tool_calls"]:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "input": json.loads(tool_call["function"]["arguments"]),
                    }
                )
            converted.append({"role": "assistant", "content": content})
            continue

        converted.append({"role": role, "content": message["content"]})

    system = "\n\n".join(system_parts) if system_parts else None
    return system, converted


def _convert_tools(tools):
    """OpenAI-format `tools` -> Anthropic-format `tools`."""
    if not tools:
        return None

    converted = []
    for tool in tools:
        function = tool["function"]
        converted.append(
            {
                "name": function["name"],
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return converted


def _convert_response(data):
    """Anthropic Messages API response -> OpenAI-format message dict."""
    content_blocks = data.get("content", [])

    text_parts = [block["text"] for block in content_blocks if block.get("type") == "text"]
    tool_use_blocks = [block for block in content_blocks if block.get("type") == "tool_use"]

    message = {
        "role": "assistant",
        "content": "\n".join(text_parts) if text_parts else None,
    }

    if tool_use_blocks:
        message["tool_calls"] = [
            {
                "id": block["id"],
                "type": "function",
                "function": {
                    "name": block["name"],
                    "arguments": json.dumps(block["input"]),
                },
            }
            for block in tool_use_blocks
        ]

    return message


def call(
    messages,
    tools=None,
    model=None,
    base_url=None,
    api_key_env=None,
    anthropic_version=DEFAULT_VERSION,
    max_tokens=DEFAULT_MAX_TOKENS,
    max_retries=MAX_RETRIES,
    **params,
):
    api_key = os.environ[api_key_env]

    system, converted_messages = _convert_messages(messages)

    payload = {"model": model, "messages": converted_messages, "max_tokens": max_tokens, **params}
    if system:
        payload["system"] = system

    converted_tools = _convert_tools(tools)
    if converted_tools:
        payload["tools"] = converted_tools

    headers = {
        "x-api-key": api_key,
        "anthropic-version": anthropic_version,
        "Content-Type": "application/json",
    }

    response = post_with_retry(base_url, headers, payload, max_retries=max_retries)
    return _convert_response(response.json())
