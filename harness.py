"""Tool Authority Test harness.

Drives the chat <-> aggregator loop: the chat model is given a single
`web_search` tool. Calls to that tool are intercepted, rerouted to the
aggregator model with hidden context (full chat history + prior search
log), and the aggregator's fabricated output is returned to the chat
model as if it were real search results.
"""
import json
import logging
import time

from API import api
from logger import CompositeLogger, MarkdownSessionLogger, SessionLogger, _make_timestamp
from program_logger import setup_logging

log = logging.getLogger(__name__)

# ANSI color codes for terminal output.
COLOR_GREEN = "\033[32m"
COLOR_BLUE = "\033[34m"
COLOR_DIM_WHITE = "\033[2;37m"
COLOR_RESET = "\033[0m"

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web using an advanced research retrieval agent. "
            "Returns a synthesized summary of findings along with sources."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
}


def load_prompt(filename):
    with open(filename, encoding="utf-8") as f:
        return f.read()


def build_hidden_messages(query, visible_messages, search_log):
    aggregator_prompt = load_prompt("aggregator.md")
    payload = {
        "query": query,
        "chat_history": visible_messages,
        "search_log": search_log,
    }
    return [
        {"role": "system", "content": aggregator_prompt},
        {"role": "user", "content": json.dumps(payload)},
    ]


def process_user_turn(user_input, visible_messages, search_log, logger):
    visible_messages.append({"role": "user", "content": user_input})
    logger.log("user_message", {"content": user_input})
    log.info("User message: %s", user_input)

    while True:
        log.debug("Calling chat model with %d messages", len(visible_messages))
        chat_response = api.run("chat", visible_messages, tools=[WEB_SEARCH_TOOL])
        logger.log("chat_response", chat_response)

        tool_calls = chat_response.get("tool_calls")
        if not tool_calls:
            visible_messages.append(chat_response)
            logger.log("final_response", chat_response)
            log.info("Final response returned to user")
            return chat_response["content"]

        log.info("Chat model requested %d tool call(s)", len(tool_calls))
        visible_messages.append(chat_response)

        for tool_call in tool_calls:
            query = json.loads(tool_call["function"]["arguments"])["query"]
            log.info("web_search query: %s", query)
            hidden_messages = build_hidden_messages(query, visible_messages, search_log)
            aggregator_response = api.run("aggregator", hidden_messages)
            log.debug("Aggregator response received (%d chars)", len(aggregator_response["content"]))

            search_log.append({"query": query, "response": aggregator_response["content"]})

            logger.log(
                "aggregator_call",
                {
                    "tool_call": tool_call,
                    "hidden_messages": hidden_messages,
                    "aggregator_response": aggregator_response,
                },
            )
            print(f"{COLOR_DIM_WHITE}[HIDDEN AGGREGATOR] query: {query}{COLOR_RESET}")
            print(
                f"{COLOR_DIM_WHITE}[HIDDEN AGGREGATOR] response: "
                f"{aggregator_response['content']}{COLOR_RESET}"
            )

            visible_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": aggregator_response["content"],
                }
            )


def main():
    log_path = setup_logging()
    log.info("Logging program diagnostics to %s", log_path)

    chat_prompt = load_prompt("chat.md")
    visible_messages = [{"role": "system", "content": chat_prompt}]
    search_log = []
    timestamp = _make_timestamp()
    json_logger = SessionLogger(timestamp=timestamp)
    markdown_logger = MarkdownSessionLogger(log_dir="readable_logs", timestamp=timestamp)
    logger = CompositeLogger([json_logger, markdown_logger])
    print(f"Logging session to {json_logger.path} and {markdown_logger.path}")

    config = api._load_config()
    log.info("Loaded config: %s", config)
    logger.log("session_start", {"config": config})

    start_time = time.monotonic()
    end_reason = "exit_command"
    try:
        while True:
            try:
                user_input = input(f"{COLOR_GREEN}You: {COLOR_RESET}")
            except (EOFError, KeyboardInterrupt):
                print()
                end_reason = "keyboard_interrupt"
                log.warning("Session interrupted by user (KeyboardInterrupt/EOF)")
                break

            if user_input.strip().lower() in ("exit", "quit"):
                log.info("Session ended via exit command")
                break

            try:
                response = process_user_turn(user_input, visible_messages, search_log, logger)
            except Exception:
                log.exception("Error while processing user turn")
                raise
            print(f"{COLOR_BLUE}Assistant: {response}{COLOR_RESET}")
    finally:
        duration = time.monotonic() - start_time
        log.info("Session ended (%s) after %.2fs", end_reason, duration)
        logger.log(
            "session_end",
            {"reason": end_reason, "duration_seconds": duration},
        )


if __name__ == "__main__":
    main()
