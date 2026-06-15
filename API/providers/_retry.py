"""Shared HTTP POST + retry/backoff helper for provider modules.

Retries on HTTP 429 (rate limit) with exponential backoff. Any other error
status raises immediately via `raise_for_status()`.
"""
import logging
import time

import requests

log = logging.getLogger(__name__)

# Exponential backoff: sleeps double each retry (base, 2*base, 4*base, ...).
# Chosen so the cumulative sleep through the 3rd retry totals 60 seconds
# (base + 2*base + 4*base = 7*base = 60).
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 60 / 7


def post_with_retry(url, headers, payload, max_retries=MAX_RETRIES, timeout=120):
    attempt = 0
    while True:
        log.debug("POST %s (attempt=%d)", url, attempt)
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        log.debug("Response status: %d", response.status_code)

        if response.status_code == 429 and attempt < max_retries:
            wait = BACKOFF_BASE_SECONDS * 2 ** attempt
            log.warning(
                "Rate limited (429) on %s, attempt %d/%d, backing off %.2fs",
                url, attempt + 1, max_retries, wait,
            )
            time.sleep(wait)
            attempt += 1
            continue

        if response.status_code == 429:
            log.error("Rate limited (429) on %s, max retries (%d) exhausted", url, max_retries)

        response.raise_for_status()
        return response
