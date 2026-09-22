# SK Voice Agents 🎙️⚡

**Multilingual AI Voice Calling Platform for Indian Businesses**

SK Voice Agents is an enterprise-grade, low-latency AI telephone agent built with **FastAPI**, **Google Gemini**, **Sarvam AI**, and **Exotel / Twilio**. It handles automated inbound customer support, lead qualification, and appointment booking in **Telugu**, **Hindi**, and **Indian English** with human-like conversation capabilities.

---

## 🌟 Key Features

- **🧠 Google Gemini LLM Engine**: Powered by `gemini-3.5-flash-lite` with intelligent fallback (`gemini-3.6-flash`), responding in under 0.6s with natural Indian speech patterns.
- **🗣️ Multilingual Speech (Sarvam AI)**:
  - **Speech-to-Text (STT)**: Sarvam `saaras:v3` with parallel multi-language transcription across Telugu (`te-IN`), English (`en-IN`), and Hindi (`hi-IN`).
  - **Text-to-Speech (TTS)**: Sarvam Bulbul v1 with natural regional voices (Kavitha, Ishita, Ritu).
- **📞 Dual Telephony Integration**:
  - **Exotel Voicebot**: Full-duplex WebSocket streaming with raw 16-bit 8 kHz Linear PCM audio (`slin`).
  - **Twilio Media Streams**: Bi-directional 8 kHz G.711 μ-law audio streaming with DTMF and mark tracking.
- **⚡ Smart VAD & Interruption Handling**: Ring-buffered Voice Activity Detection (VAD) that captures entire phrases without clipping, supports natural conversational pauses, and instantly halts playback upon caller interruption.
- **💻 Modern Web & Admin Dashboard**:
  - **Landing Page**: Modern client-facing website with live click-to-call banners and demo booking.
  - **In-Browser Web Phone**: WebRTC/WebSocket audio simulator for testing the voice agent directly from your browser mic.
  - **Admin Console (`/admin`)**: Client management, live call logs, audio transcripts, and usage metrics.

---

## 📂 Project Structure

```text
voice-call-agent/
├── Dockerfile                  # Production container build
├── docker-compose.yml          # Container orchestration
├── render.yaml                 # Render cloud deployment config
├── vercel.json                 # Vercel serverless configuration
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Build & packaging configuration
├── main.py                     # Root entry point
├── api/
│   └── index.py                # Vercel serverless adapter
├── src/voice_call_agent/
│   ├── main.py                 # FastAPI application factory
│   ├── api/
│   │   ├── clients.py          # Client management CRUD endpoints
│   │   ├── routes.py           # Health and utility routes
│   │   ├── telephony.py        # Bi-directional WebSocket & webhooks (Exotel/Twilio)
│   │   └── vapi.py             # Optional Vapi.ai assistant setup
│   ├── agent/
│   │   ├── orchestrator.py     # Turn management, STT/LLM/TTS pipeline
│   │   ├── prompts.py          # Human persona (Kiran from Hyderabad) instructions
│   │   └── tools/              # Business tools (lead qualification, appointment booking)
│   ├── core/
│   │   └── config.py           # Pydantic Settings & dynamic environment resolution
│   ├── models/
│   │   ├── client.py           # Client schema models
│   │   └── conversation.py     # CallSession and message data models
│   ├── providers/
│   │   ├── llm/                # Gemini & ExpLabs REST clients with retry logic
│   │   ├── speech/             # Sarvam STT/TTS, codec transcoding, and VAD buffer
│   │   └── telephony/          # Exotel & Twilio provider implementations
│   └── static/                 # Frontend landing page, Web Phone, and Admin Console
└── tests/                      # Automated unit and integration test suite (32 tests)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Google Gemini API Key** (Free from [Google AI Studio](https://aistudio.google.com/apikey))
- **Sarvam AI API Key** (From [Sarvam AI Dashboard](https://dashboard.sarvam.ai))
- **Exotel Account** (or Twilio account for telephony)

---

### Local Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sreekiran06/VoiceAgents.git
   cd VoiceAgents
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e '.[dev]'
   ```

4. **Configure Environment Variables**:
   Create a `.env` file (copied from `.env.example`):
   ```bash
   cp .env.example .env
   ```

   Fill in your API keys in `.env`:
   ```env
   APP_NAME=Voice Call Agent
   ENVIRONMENT=development
   PUBLIC_BASE_URL=http://localhost:8000

   # LLM Provider
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here

   # Sarvam AI
   SARVAM_API_KEY=your_sarvam_api_key_here
   SARVAM_DEFAULT_LANGUAGES=te-IN,en-IN,hi-IN

   # Telephony (Exotel)
   TELEPHONY_PROVIDER=exotel
   EXOTEL_ACCOUNT_SID=your_exotel_sid
   EXOTEL_API_KEY=your_exotel_key
   EXOTEL_API_TOKEN=your_exotel_token
   EXOTEL_CALLER_ID=04041892488
   EXOTEL_APP_ID=your_exotel_app_id
   ```

5. **Start the development server**:
   ```bash
   uvicorn voice_call_agent.main:app --reload --port 8000
   ```

6. **Expose locally for telephony webhooks** (using ngrok):
   ```bash
   ngrok http 8000
   ```
   *Copy your ngrok forwarding URL (e.g. `https://xxxx.ngrok-free.dev`) and set `PUBLIC_BASE_URL` in `.env`.*

---

## 🧪 Testing

Run the automated test suite with pytest:

```bash
pytest
```

Run code formatting and lint checks:

```bash
ruff check .
```

---

## 🌐 Endpoints & Web Interfaces

| URL | Description |
|---|---|
| `http://localhost:8000/` | Public Marketing Landing Page with live dialer |
| `http://localhost:8000/admin` | Admin Dashboard (Clients, Analytics, Call Logs) |
| `http://localhost:8000/docs` | OpenAPI / Swagger Interactive Documentation |
| `http://localhost:8000/health` | Healthcheck endpoint (`{"status": "ok"}`) |
| `ws://localhost:8000/telephony/media-stream` | Exotel/Twilio Bi-directional Audio WebSocket |
| `POST /telephony/exotel/status` | Exotel Call Status Webhook Callback |
| `POST /telephony/inbound` | Twilio Inbound Call Voice Webhook |

---

## ☁️ Deployment

### Option 1: Render (Cloud Backend)

1. Connect your GitHub repository to [Render](https://dashboard.render.com).
2. Create a new **Web Service**:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && pip install -e .`
   - **Start Command**: `uvicorn voice_call_agent.main:app --host 0.0.0.0 --port $PORT`
3. Add your environment variables in Render's dashboard.
4. Set your Exotel Voicebot URL to `wss://<your-render-app>.onrender.com/telephony/media-stream`.

---

### Option 2: Docker / Cloud VPS

Deploy instantly with Docker Compose:

```bash
docker compose up -d --build
```

---

### Option 3: Vercel (Frontend & Serverless)

The project includes `vercel.json` and `api/index.py` configured for one-click deployment on [Vercel](https://vercel.com). Pushing to `main` automatically triggers deployment.

---

## 🔒 Responsible AI Calling & Compliance

- **AI Disclosure**: Clearly informs callers that they are speaking with Kiran from SK Voice Agents.
- **DND & Consent**: Supports DND scrubbing and opt-out workflows compliant with TRAI / Indian telecom guidelines.
- **Secure Handling**: Audio streams and credentials are strictly isolated and never stored unencrypted.

---

## 📄 License

MIT License © 2026 SK Voice Agents.
