"""Black-box API module.

run(role, messages, tools=None) -> OpenAI-format response dict.

Dispatches to a real provider implementation based on per-role configuration
in /API/config.json.
"""
import json
import os

from dotenv import load_dotenv

from API.providers import anthropic, google, openai, openrouter, vertexai, zai, zai_coding

load_dotenv()

PROVIDERS = {
    "openrouter": openrouter.call,
    "openai": openai.call,
    "anthropic": anthropic.call,
    "google": google.call,
    "vertexai": vertexai.call,
    "zai": zai.call,
    "zai_coding": zai_coding.call,
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    config.pop("_supported_providers", None)
    return config


def run(role, messages, tools=None):
    config = _load_config()
    if role not in config:
        raise ValueError(f"Unknown role: {role!r}")

    role_config = config[role]
    provider = role_config["provider"]
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")

    params = {k: v for k, v in role_config.items() if k != "provider"}
    return PROVIDERS[provider](messages, tools=tools, **params)
