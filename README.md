# Voice Call Agent

Python + FastAPI starter structure for a telephone voice agent. Telephony,
speech, and language model integrations are intentionally open for selection.

```text
voice-call-agent/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── docs/
│   └── architecture.md
├── src/voice_call_agent/
│   ├── main.py                 # FastAPI application
│   ├── api/routes.py           # Health route; future webhooks and media routes
│   ├── core/config.py          # Environment settings
│   ├── agent/
│   │   ├── prompts.py          # Agent instructions
│   │   └── tools/             # Booking, CRM, and other agent actions
│   ├── models/conversation.py # Call state and messages
│   └── providers/
│       ├── telephony/          # Twilio / Telnyx adapters
│       ├── speech/             # Speech recognition and synthesis
│       └── llm/                # Language model interface and adapters
└── tests/                     # Test guidance
```

## Run locally

Requires Python 3.11 or newer. Run from this project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn voice_call_agent.main:app --reload
```

Open <http://localhost:8000/docs> for API documentation, or check:

```sh
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}`.

## Current scope

The application exposes a health endpoint. It does not yet place or answer
calls, process audio, or connect to an AI provider. See
[the architecture and implementation checklist](docs/architecture.md) for next steps.

Once features and tests are added, use `ruff check .` and `pytest` to check them.
