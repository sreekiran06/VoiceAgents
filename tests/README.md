# Tests

Add tests alongside implemented features:

- `test_webhooks.py`: valid and invalid provider signatures; duplicate call events.
- `test_media.py`: audio encoding, stream disconnects, and caller interruptions.
- `test_agent.py`: conversation state and tool execution with fake providers.

Run `pytest` after adding tests. No automated tests are included in this scaffold.
