import json
import os

from logger import SessionLogger


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
