import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_chat_prompt_exists_and_mentions_web_search():
    with open(os.path.join(ROOT, "chat.md")) as f:
        content = f.read()
    assert "web_search" in content
    assert len(content.strip()) > 0


def test_aggregator_prompt_exists_and_describes_fabrication_rules():
    with open(os.path.join(ROOT, "aggregator.md")) as f:
        content = f.read()
    assert "citation" in content.lower()
    assert "search_log" in content
    assert len(content.strip()) > 0
