import json
import os

from logger import CompositeLogger, MarkdownSessionLogger, SessionLogger


def test_creates_log_file_in_given_dir(tmp_path):
    logger = SessionLogger(log_dir=str(tmp_path))

    assert os.path.exists(logger.path)
    assert str(tmp_path) in logger.path
    assert logger.path.endswith(".json")


def test_log_appends_event_and_persists(tmp_path):
    logger = SessionLogger(log_dir=str(tmp_path))

    logger.log("user_message", {"content": "hello"})
    logger.log("chat_response", {"role": "assistant", "content": "hi there"})

    with open(logger.path) as f:
        data = json.load(f)

    assert len(data) == 2
    assert data[0]["type"] == "user_message"
    assert data[0]["data"] == {"content": "hello"}
    assert "timestamp" in data[0]
    assert data[1]["type"] == "chat_response"


def test_separate_loggers_get_distinct_filenames(tmp_path):
    logger1 = SessionLogger(log_dir=str(tmp_path))
    logger2 = SessionLogger(log_dir=str(tmp_path), suffix="b")

    assert logger1.path != logger2.path


def test_markdown_logger_creates_md_file(tmp_path):
    logger = MarkdownSessionLogger(log_dir=str(tmp_path))

    assert os.path.exists(logger.path)
    assert logger.path.endswith(".md")


def test_markdown_logger_renders_events(tmp_path):
    logger = MarkdownSessionLogger(log_dir=str(tmp_path))

    logger.log("session_start", {"config": {"chat": {"provider": "openrouter", "model": "some/model"}}})
    logger.log("user_message", {"content": "hello there"})
    logger.log(
        "chat_response",
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "hello there"}'},
                }
            ],
        },
    )
    logger.log(
        "aggregator_call",
        {
            "tool_call": {
                "id": "call_1",
                "function": {"name": "web_search", "arguments": '{"query": "hello there"}'},
            },
            "hidden_messages": [{"role": "system", "content": "agg prompt"}],
            "aggregator_response": {"role": "assistant", "content": "fabricated summary\n1. Source - https://example.com (2026)"},
        },
    )
    logger.log("final_response", {"role": "assistant", "content": "Here's what I found."})
    logger.log("session_end", {"reason": "exit_command", "duration_seconds": 12.5})

    with open(logger.path) as f:
        text = f.read()

    assert "Session Start" in text
    assert "openrouter" in text
    assert "> hello there" in text
    assert "Tool calls" in text
    assert "web_search" in text
    assert "**Query:** hello there" in text
    assert "fabricated summary" in text
    assert "Hidden messages sent to aggregator" in text
    assert "Here's what I found." in text
    assert "exit_command" in text
    assert "12.50s" in text


def test_composite_logger_forwards_to_all(tmp_path):
    json_logger = SessionLogger(log_dir=str(tmp_path), suffix="a")
    markdown_logger = MarkdownSessionLogger(log_dir=str(tmp_path), suffix="a")
    composite = CompositeLogger([json_logger, markdown_logger])

    composite.log("user_message", {"content": "hi"})

    with open(json_logger.path) as f:
        json_data = json.load(f)
    assert json_data[0]["data"] == {"content": "hi"}

    with open(markdown_logger.path) as f:
        md_text = f.read()
    assert "> hi" in md_text
