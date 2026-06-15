import json
import os

import harness
from logger import SessionLogger


def test_full_mock_loop_produces_log_with_fake_citations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

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
