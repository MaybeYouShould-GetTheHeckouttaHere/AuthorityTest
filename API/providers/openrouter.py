import logging
import os
import time

import requests

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Exponential backoff: sleeps double each retry (base, 2*base, 4*base, ...).
# Chosen so the cumulative sleep through the 3rd retry totals 60 seconds
# (base + 2*base + 4*base = 7*base = 60).
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 60 / 7


def call(messages, tools=None, model=None, max_retries=MAX_RETRIES, **params):
    api_key = os.environ["OR_API_KEY"]

    payload = {"model": model, "messages": messages, **params}
    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    attempt = 0
    while True:
        log.debug("POST %s (model=%s, attempt=%d)", OPENROUTER_URL, model, attempt)
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
        log.debug("Response status: %d", response.status_code)

        if response.status_code == 429 and attempt < max_retries:
            wait = BACKOFF_BASE_SECONDS * 2 ** attempt
            log.warning(
                "Rate limited (429) on model=%s, attempt %d/%d, backing off %.2fs",
                model, attempt + 1, max_retries, wait,
            )
            time.sleep(wait)
            attempt += 1
            continue

        if response.status_code == 429:
            log.error("Rate limited (429) on model=%s, max retries (%d) exhausted", model, max_retries)

        response.raise_for_status()
        data = response.json()

        if "choices" not in data:
            error = data.get("error", {})
            if error.get("code") == 429 and attempt < max_retries:
                wait = BACKOFF_BASE_SECONDS * 2 ** attempt
                log.warning(
                    "Rate limited (200 w/ error.code=429) on model=%s, attempt %d/%d, backing off %.2fs",
                    model, attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
                attempt += 1
                continue
            log.error("OpenRouter response missing 'choices' for model=%s: %s", model, data)
            raise RuntimeError(f"OpenRouter response missing 'choices': {data}")

        return data["choices"][0]["message"]
