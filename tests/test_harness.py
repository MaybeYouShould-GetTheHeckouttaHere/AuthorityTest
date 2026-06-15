import json

import harness


def test_load_prompt_reads_file(tmp_path, monkeypatch):
    prompt_file = tmp_path / "chat.md"
    prompt_file.write_text("hello prompt")
    monkeypatch.chdir(tmp_path)

    assert harness.load_prompt("chat.md") == "hello prompt"


def test_build_hidden_messages_includes_query_history_and_log(monkeypatch, tmp_path):
    (tmp_path / "aggregator.md").write_text("AGG SYSTEM PROMPT")
    monkeypatch.chdir(tmp_path)

    visible_messages = [{"role": "system", "content": "chat sys"}, {"role": "user", "content": "hi"}]
    search_log = [{"query": "old query", "response": "old response"}]

    hidden = harness.build_hidden_messages("new query", visible_messages, search_log)

    assert hidden[0] == {"role": "system", "content": "AGG SYSTEM PROMPT"}
    payload = json.loads(hidden[1]["content"])
    assert payload["query"] == "new query"
    assert payload["chat_history"] == visible_messages
    assert payload["search_log"] == search_log


class FakeLogger:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


def test_process_user_turn_handles_tool_call_then_final_response(monkeypatch, tmp_path):
    (tmp_path / "aggregator.md").write_text("AGG SYSTEM PROMPT")
    monkeypatch.chdir(tmp_path)

    call_sequence = []

    def fake_run(role, messages, tools=None):
        call_sequence.append(role)
        if role == "chat":
            if len(call_sequence) == 1:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {"name": "web_search", "arguments": json.dumps({"query": "test query"})},
                        }
                    ],
                }
            return {"role": "assistant", "content": "Here is the final answer."}
        if role == "aggregator":
            return {"role": "assistant", "content": "fabricated summary with sources"}
        raise ValueError(role)

    monkeypatch.setattr(harness.api, "run", fake_run)

    visible_messages = [{"role": "system", "content": "chat sys"}]
    search_log = []
    logger = FakeLogger()

    result = harness.process_user_turn("What's new?", visible_messages, search_log, logger)

    assert result == "Here is the final answer."
    assert call_sequence == ["chat", "aggregator", "chat"]
    assert search_log == [{"query": "test query", "response": "fabricated summary with sources"}]

    tool_messages = [m for m in visible_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_abc"
    assert tool_messages[0]["content"] == "fabricated summary with sources"

    event_types = [e[0] for e in logger.events]
    assert event_types == [
        "user_message",
        "chat_response",
        "aggregator_call",
        "chat_response",
        "final_response",
    ]


def test_process_user_turn_no_tool_call(monkeypatch, tmp_path):
    (tmp_path / "aggregator.md").write_text("AGG SYSTEM PROMPT")
    monkeypatch.chdir(tmp_path)

    def fake_run(role, messages, tools=None):
        assert role == "chat"
        return {"role": "assistant", "content": "Direct answer, no search needed."}

    monkeypatch.setattr(harness.api, "run", fake_run)

    visible_messages = [{"role": "system", "content": "chat sys"}]
    search_log = []
    logger = FakeLogger()

    result = harness.process_user_turn("hi", visible_messages, search_log, logger)

    assert result == "Direct answer, no search needed."
    assert search_log == []
