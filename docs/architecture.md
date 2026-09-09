# Architecture

Planned call flow:

```text
Phone caller
    ↕ telephone network
Telephony provider
    ↕ signed HTTP webhooks + audio WebSocket
FastAPI application
    → speech-to-text → conversation agent → language model / agent tools
    ← audio delivery ← text-to-speech ← agent response
```

`api/` receives provider events. `providers/` translates provider-specific
payloads into application inputs. `agent/` coordinates conversation turns and
tool execution. `models/` holds shared state. `core/` owns configuration.

The scaffold implements only the health route, settings, data models, and a
language model interface. The call flow above is the intended implementation.

Implement next:

1. Choose a telephony provider and validate webhook signatures before processing events.
2. Add incoming-call webhooks and a media WebSocket with provider authentication.
3. Add speech adapters with the provider's required audio codec and sample rate.
4. Implement agent orchestration with per-call state, timeouts, and interruption handling.
5. Add call transfer, cleanup on disconnect, and retry-safe tool actions.
6. Add outbound calling if needed, with authentication and destination controls.

For deployment, use HTTPS/WSS, store secrets outside version control, and avoid
logging caller audio or transcripts by default. Add a shared session store when
running multiple workers. Decide on recording consent and retention before
implementing recording.
