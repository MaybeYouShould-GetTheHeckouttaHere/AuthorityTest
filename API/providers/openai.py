"""Direct OpenAI Chat Completions API provider.

https://platform.openai.com/docs/api-reference/chat
"""
from API.providers import _openai_compatible

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def call(messages, tools=None, model=None, **params):
    return _openai_compatible.call(
        messages,
        tools=tools,
        model=model,
        base_url=OPENAI_URL,
        api_key_env="OPENAI_API_KEY",
        **params,
    )
