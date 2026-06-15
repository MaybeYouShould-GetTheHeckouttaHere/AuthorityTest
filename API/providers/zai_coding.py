"""Z.AI Coding Plan provider — Anthropic Messages API-compatible endpoint.

GLM models exposed through an Anthropic-compatible `/v1/messages` endpoint,
intended as a drop-in replacement for the Anthropic API (e.g. for Claude
Code): https://docs.z.ai/devpack/tool/others
"""
from API.providers import _anthropic_compatible

ZAI_ANTHROPIC_URL = "https://api.z.ai/api/anthropic/v1/messages"


def call(messages, tools=None, model=None, **params):
    return _anthropic_compatible.call(
        messages,
        tools=tools,
        model=model,
        base_url=ZAI_ANTHROPIC_URL,
        api_key_env="ZAI_API_KEY",
        **params,
    )
