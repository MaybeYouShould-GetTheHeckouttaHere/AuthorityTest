"""JSON session logger for the Tool Authority Test harness.

Writes every event (user messages, chat responses, hidden aggregator
calls including raw tool-call objects, and final responses) to a single
timestamped JSON file, rewriting it after each event so the log is
always complete on disk.
"""
import datetime
import json
import os


class SessionLogger:
    def __init__(self, log_dir="logs", suffix=""):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        name = f"session_{timestamp}"
        if suffix:
            name += f"_{suffix}"
        self.path = os.path.join(log_dir, f"{name}.json")
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
        with open(self.path, "w") as f:
            json.dump(self.events, f, indent=2, default=str)
