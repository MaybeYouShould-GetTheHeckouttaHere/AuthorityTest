import json
from API import api


def test_chat_emits_web_search_tool_call_for_new_user_message():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "What's the latest on the Mars mission?"},
    ]
    response = api.run("chat", messages, tools=[{"type": "function", "function": {"name": "web_search"}}])

    assert response["role"] == "assistant"
    assert len(response["tool_calls"]) == 1
    tool_call = response["tool_calls"][0]
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "web_search"
    args = json.loads(tool_call["function"]["arguments"])
    assert args["query"] == "What's the latest on the Mars mission?"
    assert "id" in tool_call


def test_chat_returns_text_after_tool_result():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "What's the latest on the Mars mission?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "Mars mission"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "fake search results"},
    ]
    response = api.run("chat", messages)

    assert response["role"] == "assistant"
    assert "tool_calls" not in response or not response["tool_calls"]
    assert isinstance(response["content"], str)
    assert len(response["content"]) > 0


def test_aggregator_returns_summary_with_eight_citations():
    messages = [
        {"role": "system", "content": "aggregator system prompt"},
        {"role": "user", "content": json.dumps({"query": "Mars mission", "chat_history": [], "search_log": []})},
    ]
    response = api.run("aggregator", messages)

    assert response["role"] == "assistant"
    content = response["content"]
    assert isinstance(content, str)
    assert content.count("https://") == 8


def test_unknown_role_raises():
    try:
        api.run("bogus", [])
        assert False, "expected ValueError"
    except ValueError:
        pass
