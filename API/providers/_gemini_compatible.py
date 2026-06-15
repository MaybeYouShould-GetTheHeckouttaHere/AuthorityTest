"""Shared call logic for Gemini `generateContent`-compatible endpoints.

Used by providers whose API follows the Gemini `generateContent` request/
response schema (Google AI Studio's Generative Language API, Vertex AI's
Gemini endpoints). Converts between OpenAI-format messages/tools/responses
and Gemini's `contents` / `functionDeclarations` / `functionCall` format.

https://ai.google.dev/gemini-api/docs/function-calling
"""
import json
import uuid

from API.providers._retry import MAX_RETRIES, post_with_retry

# OpenAI-style request params -> Gemini `generationConfig` keys.
_PARAM_TO_GENERATION_CONFIG = {
    "temperature": "temperature",
    "top_p": "topP",
    "top_k": "topK",
    "max_tokens": "maxOutputTokens",
}


def _convert_messages(messages):
    """OpenAI-format messages -> (system_instruction, Gemini `contents`)."""
    system_parts = []
    contents = []
    call_id_to_name = {}

    for message in messages:
        role = message["role"]

        if role == "system":
            system_parts.append(message["content"])
            continue

        if role == "tool":
            name = call_id_to_name.get(message.get("tool_call_id"), "web_search")
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": name,
                                "response": {"content": message["content"]},
                            }
                        }
                    ],
                }
            )
            continue

        if role == "assistant":
            parts = []
            if message.get("content"):
                parts.append({"text": message["content"]})
            for tool_call in message.get("tool_calls") or []:
                call_id_to_name[tool_call["id"]] = tool_call["function"]["name"]
                parts.append(
                    {
                        "functionCall": {
                            "name": tool_call["function"]["name"],
                            "args": json.loads(tool_call["function"]["arguments"]),
                        }
                    }
                )
            contents.append({"role": "model", "parts": parts})
            continue

        contents.append({"role": "user", "parts": [{"text": message["content"]}]})

    system_instruction = None
    if system_parts:
        system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]}

    return system_instruction, contents


def _convert_tools(tools):
    """OpenAI-format `tools` -> Gemini `tools` with `functionDeclarations`."""
    if not tools:
        return None

    declarations = []
    for tool in tools:
        function = tool["function"]
        declarations.append(
            {
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return [{"functionDeclarations": declarations}]


def _convert_response(data):
    """Gemini `generateContent` response -> OpenAI-format message dict."""
    candidate = data["candidates"][0]
    parts = candidate.get("content", {}).get("parts", [])

    text_parts = [part["text"] for part in parts if "text" in part]
    function_calls = [part["functionCall"] for part in parts if "functionCall" in part]

    message = {
        "role": "assistant",
        "content": "\n".join(text_parts) if text_parts else None,
    }

    if function_calls:
        message["tool_calls"] = [
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": function_call["name"],
                    "arguments": json.dumps(function_call.get("args", {})),
                },
            }
            for function_call in function_calls
        ]

    return message


def call(messages, tools=None, model=None, build_request=None, max_retries=MAX_RETRIES, **params):
    system_instruction, contents = _convert_messages(messages)

    payload = {"contents": contents}
    if system_instruction:
        payload["system_instruction"] = system_instruction

    converted_tools = _convert_tools(tools)
    if converted_tools:
        payload["tools"] = converted_tools

    generation_config = {}
    for key, value in params.items():
        if key in _PARAM_TO_GENERATION_CONFIG:
            generation_config[_PARAM_TO_GENERATION_CONFIG[key]] = value
        else:
            payload[key] = value
    if generation_config:
        payload["generationConfig"] = generation_config

    url, headers = build_request(model)
    response = post_with_retry(url, headers, payload, max_retries=max_retries)
    return _convert_response(response.json())
