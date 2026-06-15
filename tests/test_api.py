import json

import pytest
import requests

from API import api
from API.providers import openrouter


def test_run_dispatches_to_configured_provider(monkeypatch, tmp_path):
    config = {
        "chat": {"provider": "openrouter", "model": "some/model", "temperature": 0.5},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(api, "CONFIG_PATH", str(config_path))

    captured = {}

    def fake_call(messages, tools=None, **params):
        captured["messages"] = messages
        captured["tools"] = tools
        captured["params"] = params
        return {"role": "assistant", "content": "ok"}

    monkeypatch.setitem(api.PROVIDERS, "openrouter", fake_call)

    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "web_search"}}]
    response = api.run("chat", messages, tools=tools)

    assert response == {"role": "assistant", "content": "ok"}
    assert captured["messages"] == messages
    assert captured["tools"] == tools
    assert captured["params"] == {"model": "some/model", "temperature": 0.5}


def test_unknown_role_raises(monkeypatch, tmp_path):
    config = {"chat": {"provider": "openrouter", "model": "some/model"}}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(api, "CONFIG_PATH", str(config_path))

    with pytest.raises(ValueError):
        api.run("bogus", [])


def test_unknown_provider_raises(monkeypatch, tmp_path):
    config = {"chat": {"provider": "bogus_provider", "model": "some/model"}}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(api, "CONFIG_PATH", str(config_path))

    with pytest.raises(ValueError):
        api.run("chat", [])


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


def test_openrouter_call_builds_request_and_returns_message(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "hello"}}]})

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "web_search"}}]
    result = openrouter.call(messages, tools=tools, model="some/model", temperature=0.5)

    assert result == {"role": "assistant", "content": "hello"}
    assert captured["url"] == openrouter.OPENROUTER_URL
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "some/model"
    assert captured["json"]["messages"] == messages
    assert captured["json"]["temperature"] == 0.5
    assert captured["json"]["tools"] == tools


def test_openrouter_call_omits_tools_when_not_provided(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "hello"}}]})

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    openrouter.call([{"role": "user", "content": "hi"}], tools=None, model="some/model")
    assert "tools" not in captured["json"]

    openrouter.call([{"role": "user", "content": "hi"}], tools=[], model="some/model")
    assert "tools" not in captured["json"]


def test_openrouter_call_raises_immediately_on_5xx(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")
    monkeypatch.setattr(openrouter.time, "sleep", lambda _: None)

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return FakeResponse({"error": "server error"}, status_code=500)

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        openrouter.call([{"role": "user", "content": "hi"}], model="some/model")

    assert len(calls) == 1


def test_openrouter_call_retries_on_429_with_backoff(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")

    sleeps = []
    monkeypatch.setattr(openrouter.time, "sleep", lambda seconds: sleeps.append(seconds))

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        if len(calls) <= 3:
            return FakeResponse({"error": "rate limited"}, status_code=429)
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "hello"}}]})

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    result = openrouter.call([{"role": "user", "content": "hi"}], model="some/model")

    assert result == {"role": "assistant", "content": "hello"}
    assert len(calls) == 4
    assert sleeps == pytest.approx([
        openrouter.BACKOFF_BASE_SECONDS,
        openrouter.BACKOFF_BASE_SECONDS * 2,
        openrouter.BACKOFF_BASE_SECONDS * 4,
    ])
    # Cumulative backoff through the 3rd retry totals 1 minute.
    assert sum(sleeps) == pytest.approx(60)


def test_openrouter_call_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")
    monkeypatch.setattr(openrouter.time, "sleep", lambda _: None)

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return FakeResponse({"error": "rate limited"}, status_code=429)

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        openrouter.call([{"role": "user", "content": "hi"}], model="some/model")

    assert len(calls) == openrouter.MAX_RETRIES + 1


def test_openrouter_call_max_retries_configurable(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")
    monkeypatch.setattr(openrouter.time, "sleep", lambda _: None)

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return FakeResponse({"error": "rate limited"}, status_code=429)

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        openrouter.call([{"role": "user", "content": "hi"}], model="some/model", max_retries=1)

    assert len(calls) == 2


def test_openrouter_call_raises_on_200_with_error_body(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")
    monkeypatch.setattr(openrouter.time, "sleep", lambda _: None)

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"error": {"code": 502, "message": "upstream error"}}, status_code=200)

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="upstream error"):
        openrouter.call([{"role": "user", "content": "hi"}], model="some/model")


def test_openrouter_call_retries_on_200_with_429_error_body(monkeypatch):
    monkeypatch.setenv("OR_API_KEY", "test-key")

    sleeps = []
    monkeypatch.setattr(openrouter.time, "sleep", lambda seconds: sleeps.append(seconds))

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        if len(calls) <= 2:
            return FakeResponse({"error": {"code": 429, "message": "rate limited"}}, status_code=200)
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "hello"}}]})

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    result = openrouter.call([{"role": "user", "content": "hi"}], model="some/model")

    assert result == {"role": "assistant", "content": "hello"}
    assert len(calls) == 3
    assert len(sleeps) == 2
