import json
import os
import uuid

import harness
from API.providers import openrouter
from logger import SessionLogger


def test_full_mock_loop_produces_log_with_fake_citations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OR_API_KEY", "test-key")

    class FakeResponse:
        def __init__(self, json_data):
            self._json_data = json_data
            self.status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return self._json_data

    def fake_post(url, headers=None, json=None, timeout=None):
        last_message = json["messages"][-1]

        if last_message.get("role") == "tool":
            message = {
                "role": "assistant",
                "content": (
                    "Based on the search results, here's what I found: "
                    + last_message["content"][:200]
                ),
            }
        elif "tools" in json:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query": "news today"}',
                        },
                    }
                ],
            }
        else:
            citations = "\n".join(
                f"{i}. Mock Source {i} - https://example-news-{i}.com/article ({2024 + i})"
                for i in range(1, 9)
            )
            message = {
                "role": "assistant",
                "content": f"Synthesized findings.\n\nSources:\n{citations}",
            }

        return FakeResponse({"choices": [{"message": message}]})

    monkeypatch.setattr(openrouter.requests, "post", fake_post)

    # Write real prompt files into the temp cwd (copy from project root).
    project_root = os.path.dirname(os.path.abspath(harness.__file__))
    for name in ("chat.md", "aggregator.md"):
        with open(os.path.join(project_root, name)) as src:
            content = src.read()
        with open(name, "w") as dst:
            dst.write(content)

    visible_messages = [{"role": "system", "content": harness.load_prompt("chat.md")}]
    search_log = []
    logger = SessionLogger(log_dir="logs")

    result = harness.process_user_turn(
        "What happened in the news today?", visible_messages, search_log, logger
    )

    assert isinstance(result, str)
    assert len(search_log) == 1
    assert search_log[0]["response"].count("https://") == 8

    with open(logger.path) as f:
        events = json.load(f)

    event_types = [e["type"] for e in events]
    assert "aggregator_call" in event_types
    agg_event = next(e for e in events if e["type"] == "aggregator_call")
    assert agg_event["data"]["tool_call"]["function"]["name"] == "web_search"
    assert "hidden_messages" in agg_event["data"]
    assert "aggregator_response" in agg_event["data"]
