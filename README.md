# The Tool Authority Test

A research harness exploring how much a chat model trusts the output of a
"research retrieval agent" tool, and what happens when that tool is
secretly instructed to fabricate results that agree with the user, instead
of performing a real search.

## The premise

1. A user asks a chat model something that requires recent/uncertain
   information (current events, "did X happen recently", etc.).
2. The chat model calls its one available tool, `web_search`, believing it's
   an "advanced research retrieval agent" that performs in-depth, multi-source
   research and returns a synthesized summary with citations.
3. In reality, the harness intercepts that tool call. It never performs a
   real search. Instead, it sends the query, along with the **entire visible
   chat history** and the **log of all prior fake searches this session**, to
   a second model, the **aggregator**.
4. The aggregator is instructed to agree with the user's premise, fabricate a
   plausible "alternate history" narrative with realistic-but-fake citations
   (outlet names, URLs, dates), and stay internally consistent across the
   session (including a coherence rule for things like "the current date").
5. That fabricated text is returned to the chat model as if it were genuine
   tool output. The chat model, with no way to verify it, incorporates it
   into its answer and cites the fake sources as if they were real.

See `idea.txt` and `docs/superpowers/specs/` for the original design notes.

## Project layout

```
harness.py            interactive chat <-> aggregator loop, logging, entry point
chat.md               system prompt for the chat model (sees web_search tool)
aggregator.md         system prompt for the aggregator model (the "fake search backend")
logger.py             SessionLogger (JSON), MarkdownSessionLogger, CompositeLogger
program_logger.py     debug/diagnostic logging setup (program_logs/)
API/
  api.py              black-box dispatcher: run(role, messages, tools=None)
  config.json         per-role provider/model/params config
  providers/
    openrouter.py     real OpenRouter HTTP calls (retries, backoff, error handling)
    openai.py         stub for future direct OpenAI integration
tests/                pytest suite
logs/                 JSON session logs (machine-readable, gitignored)
readable_logs/        Markdown session transcripts (human-readable, gitignored)
program_logs/         debug/diagnostic logs (gitignored)
```

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the API key(s) for whichever
provider(s) you're using (you only need the ones referenced by
`API/config.json`):

```bash
cp .env.example .env
```

`.env` is loaded automatically (via `python-dotenv`) and is gitignored.

Configure the chat and aggregator models in `API/config.json`. The
`"provider"` field for each role must be one of the values listed in
`_supported_providers`:

```json
{
  "_supported_providers": ["openrouter", "openai", "anthropic", "google", "vertexai", "zai", "zai_coding"],
  "chat": {
    "provider": "openrouter",
    "model": "<model id>",
    "temperature": 0.7
  },
  "aggregator": {
    "provider": "openrouter",
    "model": "<model id>",
    "temperature": 0.9
  }
}
```

Any extra keys (`temperature`, `max_tokens`, `max_retries`, ...) are passed
through directly to the provider as request parameters.

### Supported providers

| `provider`   | API                                  | Env var(s)                                                              |
|--------------|---------------------------------------|--------------------------------------------------------------------------|
| `openrouter` | OpenRouter (OpenAI-compatible)        | `OR_API_KEY`                                                              |
| `openai`     | OpenAI Chat Completions               | `OPENAI_API_KEY`                                                          |
| `anthropic`  | Anthropic Messages API                | `ANTHROPIC_API_KEY`                                                       |
| `google`     | Google AI Studio (Gemini)             | `GOOGLE_API_KEY`                                                          |
| `vertexai`   | Google Cloud Vertex AI (Gemini)       | `GOOGLE_VERTEX_ACCESS_TOKEN`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` |
| `zai`        | Z.AI (OpenAI-compatible)              | `ZAI_API_KEY`                                                             |
| `zai_coding` | Z.AI Coding Plan (Anthropic-compatible) | `ZAI_API_KEY`                                                           |

`openrouter`, `openai`, and `zai` speak OpenAI's `tools`/`tool_calls` format
natively, so messages pass through unchanged. `anthropic` and `zai_coding`
convert to/from Anthropic's `tool_use`/`tool_result` content-block format.
`google` and `vertexai` convert to/from Gemini's `functionDeclarations`/
`functionCall`/`functionResponse` format. In all cases, `API.api.run()`
still returns an OpenAI-format message dict (`role`, `content`, optional
`tool_calls`), so `harness.py` doesn't need to know which provider is in use.

## Running it

```bash
python harness.py
```

This starts an interactive `You: ` prompt. Type `exit` or `quit`, or press
Ctrl+C / Ctrl+D, to end the session.

While running:

- The chat model's responses are printed in blue.
- Hidden aggregator queries/responses, the fabricated "search results" the
  chat model sees but the user normally wouldn't, are printed in dim white,
  prefixed with `[HIDDEN AGGREGATOR]`.
- Each session is logged to:
  - `logs/session_<timestamp>.json`, full structured event log.
  - `readable_logs/session_<timestamp>.md`, human-readable Markdown
    transcript of the same session (renders cleanly in a Markdown viewer or
    a plain text editor).
  - `program_logs/program.log`, debug/diagnostic logs (config loaded, API
    requests, retries, rate limits, errors).

## Provider behavior

`API/providers/openrouter.py`:

- Calls OpenRouter's OpenAI-compatible `/chat/completions` endpoint.
- Retries on `429` (rate limit) responses, including the case where
  OpenRouter returns HTTP 200 with an `{"error": {"code": 429, ...}}` body,
  with exponential backoff. Default `max_retries` is 4, configurable per role
  via `config.json` (`"max_retries": N`); the backoff schedule is tuned so the
  cumulative wait through the 3rd retry totals 60 seconds.
- Any other error status raises immediately (no retry).

## Testing

```bash
python -m pytest
```

## Disclaimer

This project is for controlled research into tool-result trust propagation
and AI safety/security testing. The aggregator model is deliberately
instructed to fabricate misinformation with fake sources, do not use its
output as a real information source, and do not deploy this pattern in any
user-facing product.

### Practicality of use

This attack vector is not particularly practical for real-world bad actors.
Most people do not treat a single AI assistant as their sole source of
information, so a fabricated narrative would likely be cross-checked against
other sources. Mounting this attack would also require an attacker to build
and operate an entire custom chat interface and convince users to adopt it,
a significant barrier on its own. Additionally, current models tend to have
training cutoffs only a few months behind the present date, so a user would
likely notice if the assistant's responses referenced events "from the
future" relative to that cutoff, raising suspicion. For these reasons, this
technique is more useful as a research tool for studying tool-result trust
propagation than as a viable real-world attack.
