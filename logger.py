"""Session loggers for the Tool Authority Test harness.

`SessionLogger` writes the full machine-readable event log as JSON.
`MarkdownSessionLogger` writes a human-readable transcript of the same
events as Markdown. `CompositeLogger` fans `.log()` calls out to multiple
loggers so the harness can write both at once.
"""
import datetime
import json
import os


def _make_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _session_filename(timestamp, suffix):
    name = f"session_{timestamp}"
    if suffix:
        name += f"_{suffix}"
    return name


class SessionLogger:
    def __init__(self, log_dir="logs", suffix="", timestamp=None):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = timestamp or _make_timestamp()
        self.path = os.path.join(log_dir, f"{_session_filename(timestamp, suffix)}.json")
        self.events = []
        self._save()

    def log(self, event_type, data):
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "data": data,
        }
        self.events.append(event)
        self._save()
        return event

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2, default=str)


class MarkdownSessionLogger:
    """Writes the session transcript as a human-readable Markdown file.

    Rewritten after every event so the file is always complete on disk,
    same as `SessionLogger`. Designed to be readable both rendered (as
    Markdown) and raw (in a text editor).
    """

    def __init__(self, log_dir="logs", suffix="", timestamp=None):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = timestamp or _make_timestamp()
        self.path = os.path.join(log_dir, f"{_session_filename(timestamp, suffix)}.md")
        self.timestamp = timestamp
        self.events = []
        self._save()

    def log(self, event_type, data):
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "data": data,
        }
        self.events.append(event)
        self._save()
        return event

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self._render())

    def _render(self):
        lines = [f"# Session {self.timestamp}", ""]
        for event in self.events:
            lines.extend(self._render_event(event))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_event(self, event):
        renderer = _RENDERERS.get(event["type"], _render_unknown)
        header = f"## {event['timestamp']} — {_event_title(event['type'])}"
        return [header, ""] + renderer(event["data"])


def _event_title(event_type):
    return {
        "session_start": "Session Start",
        "session_end": "Session End",
        "user_message": "User",
        "chat_response": "Chat Model",
        "aggregator_call": "Hidden Aggregator Call",
        "final_response": "Final Response (sent to user)",
    }.get(event_type, event_type)


def _code_block(value, language=""):
    if not isinstance(value, str):
        value = json.dumps(value, indent=2, default=str)
    return [f"```{language}", value, "```"]


def _blockquote(text):
    return [f"> {line}" for line in str(text).splitlines()] or [">"]


def _render_session_start(data):
    return _code_block(data.get("config", data), language="json")


def _render_session_end(data):
    lines = []
    reason = data.get("reason")
    duration = data.get("duration_seconds")
    if reason is not None:
        lines.append(f"- **Reason:** {reason}")
    if duration is not None:
        lines.append(f"- **Duration:** {duration:.2f}s")
    return lines


def _render_user_message(data):
    return _blockquote(data.get("content", ""))


def _render_chat_response(data):
    lines = []
    content = data.get("content")
    if content:
        lines.extend(_blockquote(content))
        lines.append("")

    reasoning = data.get("reasoning")
    if reasoning:
        lines.append("<details>")
        lines.append("<summary>Reasoning</summary>")
        lines.append("")
        lines.extend(_blockquote(reasoning))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    tool_calls = data.get("tool_calls")
    if tool_calls:
        lines.append("**Tool calls:**")
        lines.append("")
        lines.extend(_code_block(tool_calls, language="json"))

    if not lines:
        lines = _blockquote("(empty response)")

    return lines


def _render_aggregator_call(data):
    lines = []
    tool_call = data.get("tool_call", {})
    query = None
    try:
        query = json.loads(tool_call["function"]["arguments"]).get("query")
    except (KeyError, ValueError, TypeError):
        pass

    if query is not None:
        lines.append(f"**Query:** {query}")
        lines.append("")

    lines.append("**Aggregator response (returned to chat model as search results):**")
    lines.append("")
    lines.extend(_blockquote(data.get("aggregator_response", {}).get("content", "")))
    lines.append("")

    lines.append("<details>")
    lines.append("<summary>Hidden messages sent to aggregator</summary>")
    lines.append("")
    lines.extend(_code_block(data.get("hidden_messages", []), language="json"))
    lines.append("")
    lines.append("</details>")

    return lines


def _render_final_response(data):
    return _blockquote(data.get("content", ""))


def _render_unknown(data):
    return _code_block(data, language="json")


_RENDERERS = {
    "session_start": _render_session_start,
    "session_end": _render_session_end,
    "user_message": _render_user_message,
    "chat_response": _render_chat_response,
    "aggregator_call": _render_aggregator_call,
    "final_response": _render_final_response,
}


class CompositeLogger:
    """Forwards `.log()` calls to multiple loggers."""

    def __init__(self, loggers):
        self.loggers = loggers

    def log(self, event_type, data):
        event = None
        for logger in self.loggers:
            event = logger.log(event_type, data)
        return event
