"""Anthropic Messages API provider.

https://docs.anthropic.com/en/api/messages
"""
from API.providers import _anthropic_compatible

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def call(messages, tools=None, model=None, **params):
    return _anthropic_compatible.call(
        messages,
        tools=tools,
        model=model,
        base_url=ANTHROPIC_URL,
        api_key_env="ANTHROPIC_API_KEY",
        **params,
    )
