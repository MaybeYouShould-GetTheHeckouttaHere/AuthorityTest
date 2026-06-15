"""Debug/diagnostic logging setup, separate from the session transcript logs.

Writes to `program_logs/program.log` (and echoes warnings/errors to the
console) using the standard `logging` module. Call `setup_logging()` once
at program startup; modules then use `logging.getLogger(__name__)`.
"""
import logging
import os

LOG_DIR = "program_logs"
LOG_FILE = "program.log"


def setup_logging(level=logging.DEBUG, log_dir=LOG_DIR):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, LOG_FILE)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    return log_path
