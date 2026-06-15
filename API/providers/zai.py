"""Z.AI (Zhipu AI) OpenAI-compatible API provider.

GLM models exposed through an OpenAI-compatible `/chat/completions`
endpoint: https://docs.z.ai/guides/develop/openai/python
"""
from API.providers import _openai_compatible

ZAI_URL = "https://api.z.ai/api/paas/v4/chat/completions"


def call(messages, tools=None, model=None, **params):
    return _openai_compatible.call(
        messages,
        tools=tools,
        model=model,
        base_url=ZAI_URL,
        api_key_env="ZAI_API_KEY",
        **params,
    )
