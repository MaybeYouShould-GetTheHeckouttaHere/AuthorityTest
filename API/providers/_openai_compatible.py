"""Shared call logic for OpenAI-compatible `/chat/completions` endpoints.

Used by providers whose API is a drop-in match for OpenAI's Chat Completions
schema (OpenAI itself, OpenRouter, Z.AI's `/api/paas/v4` endpoint, etc).
Messages and `tools` are already in OpenAI format, so no conversion is
needed in either direction.
"""
import os

from API.providers._retry import MAX_RETRIES, post_with_retry


def call(messages, tools=None, model=None, base_url=None, api_key_env=None, max_retries=MAX_RETRIES, **params):
    api_key = os.environ[api_key_env]

    payload = {"model": model, "messages": messages, **params}
    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = post_with_retry(base_url, headers, payload, max_retries=max_retries)
    data = response.json()
    return data["choices"][0]["message"]
