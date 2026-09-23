# SK Voice Agents 🎙️⚡

**Enterprise Multi-Tenant AI Voice Calling Platform for Indian Businesses**

SK Voice Agents is a secure, high-performance multi-tenant AI telephone agent platform built with **FastAPI**, **Google Gemini**, **Sarvam AI**, and **Exotel / Twilio**. It enables Indian businesses across industries to deploy personalized, multilingual voice agents that handle inbound support, lead qualification, and appointment booking in **Telugu**, **Hindi**, and **Indian English** with sub-second response latency.

---

## 🌟 Key Features

- **🏢 True Multi-Tenant Architecture**: Single unified platform hosting multiple clients with dedicated businesses, custom personas, tailored knowledge bases, business hours, and phone number routing.
- **⚡ Zero Per-Frame Latency Overhead**: Single-query `BusinessContext` resolution at call start with in-memory 5-minute LRU caching—zero database queries during active audio streaming.
- **🧠 Google Gemini LLM Engine**: Powered by `gemini-3.5-flash-lite` with intelligent fallback (`gemini-3.6-flash`), responding in under 0.6s with natural Indian speech patterns.
- **🗣️ Multilingual Speech (Sarvam AI)**:
  - **Speech-to-Text (STT)**: Sarvam `saaras:v3` with parallel multi-language transcription across Telugu (`te-IN`), English (`en-IN`), and Hindi (`hi-IN`).
  - **Text-to-Speech (TTS)**: Sarvam Bulbul v1 with natural regional voices (Kavitha, Ishita, Ritu).
- **📞 Dual Telephony Integration**:
  - **Exotel Voicebot**: Full-duplex WebSocket streaming with raw 16-bit 8 kHz Linear PCM audio (`slin`).
  - **Twilio Media Streams**: Bi-directional 8 kHz G.711 μ-law audio streaming with DTMF and mark tracking.
- **🏭 Industry-Specific Prompt Engine**: Dynamic persona generation for Real Estate, Healthcare, Education, Restaurants, Hotels, Home Services, and E-commerce.
- **⚡ Smart VAD & Interruption Handling**: Ring-buffered Voice Activity Detection (VAD) that captures entire phrases without clipping, supports natural conversational pauses, and instantly halts playback upon caller interruption.
- **🔐 Gated Admin Console (`/admin`)**: Independent, secure admin portal protected with JWT authentication for client management, live call logs, audio transcripts, business configuration, and platform analytics.
- **💻 Modern Public Website**: Customer-facing landing page with live dialer banners, product tour, and interactive in-browser audio test simulator.

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
│   ├── main.py                 # FastAPI application factory & DB lifecycle
│   ├── api/
│   │   ├── analytics.py        # Platform overview & call analytics API
│   │   ├── auth_routes.py      # Admin JWT login & client API keys
│   │   ├── businesses.py       # Multi-tenant Business CRUD endpoints
│   │   ├── clients.py          # Client management CRUD endpoints
│   │   ├── knowledge.py        # Business FAQ & knowledge base CRUD
│   │   ├── routes.py           # Health and utility routes
│   │   ├── telephony.py        # Bi-directional WebSocket & webhooks (Exotel/Twilio)
│   │   └── vapi.py             # Optional Vapi.ai assistant setup
│   ├── agent/
│   │   ├── orchestrator.py     # Turn management, multi-tenant STT/LLM/TTS pipeline
│   │   ├── prompt_templates.py # Dynamic industry-specific prompt generator
│   │   ├── prompts.py          # Default human persona fallback
│   │   └── tools/              # Business tools (lead qualification, appointment booking)
│   ├── core/
│   │   ├── auth.py             # Password hashing, JWT auth, and API key verification
│   │   ├── config.py           # Pydantic Settings & dynamic environment resolution
│   │   ├── context.py          # Immutable BusinessContext dataclass
│   │   ├── context_loader.py   # Phone-to-Business resolver with LRU cache
│   │   ├── database.py         # Async SQLAlchemy engine & session factory
│   │   └── seed.py             # Default admin & sample businesses seeder
│   ├── models/
│   │   ├── client.py           # Legacy Client schema models
│   │   ├── conversation.py     # CallSession and message data models
│   │   └── db_models.py        # SQLAlchemy ORM models (Admin, Client, Business, Config, Knowledge, etc.)
│   ├── providers/
│   │   ├── llm/                # Gemini & ExpLabs REST clients with retry logic
│   │   ├── speech/             # Sarvam STT/TTS, codec transcoding, and VAD buffer
│   │   └── telephony/          # Exotel & Twilio provider implementations
│   └── static/                 # Frontend landing page, Web Phone, and Admin Console
└── tests/                      # Automated unit and integration test suite (38 tests)
```

---

## 🔐 Default Super-Admin Credentials

The platform initializes the database with a pre-configured super-admin account on startup:

| Field | Default Value |
| :--- | :--- |
| **Email** | `admin@skvoiceagents.com` |
| **Password** | `admin123` |
| **Role** | `super_admin` |
| **Login URL** | `http://localhost:8000/admin` |

---

## 📡 Pre-Seeded Sample Businesses

The application automatically seeds 4 industry businesses for testing multi-tenant call routing:

| Business Name | Industry | Virtual DID | Agent Name | Supported Languages |
| :--- | :--- | :--- | :--- | :--- |
| **Sri Krishna Infra - Gachibowli** | Real Estate | `04041892488` | Kiran | Telugu, English, Hindi |
| **Apollo Clinic - Vijayawada** | Healthcare | `+91 866 244 1122` | Dr. Priya's Assistant | Telugu, English, Hindi |
| **Narayana IIT & NEET Academy** | Education | `+91 40 2345 6789` | Sneha | Telugu, English |
| **UrbanFix Home Services** | Home Services | `+91 80 0123 4567` | Rajesh | Hindi, English |

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
   DATABASE_URL=sqlite+aiosqlite:///./sk_voice_agents.db
   SECRET_KEY=sk-secret-jwt-key-for-admin-sessions-change-in-production

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
   uvicorn main:app --reload --port 8000
   ```

6. **Expose locally for telephony webhooks** (using ngrok):
   ```bash
   ngrok http 8000
   ```
   *Copy your ngrok forwarding URL (e.g. `https://xxxx.ngrok-free.dev`) and set `PUBLIC_BASE_URL` in `.env`.*

---

## 🧪 Testing

Run the full automated test suite with pytest (38 tests):

```bash
pytest
```

Run code formatting and lint checks:

```bash
ruff check .
```

---

## 🌐 Endpoints & API Reference

### Web Interfaces
| URL | Access | Description |
| :--- | :--- | :--- |
| `http://localhost:8000/` | Public | Customer marketing landing page with in-browser audio test simulator |
| `http://localhost:8000/admin` | Private (Auth Gated) | Admin Console (Clients, Businesses, Call Transcripts, KPIs) |
| `http://localhost:8000/docs` | Public | Interactive OpenAPI / Swagger documentation |
| `http://localhost:8000/health` | Public | Healthcheck endpoint (`{"status": "ok"}`) |

### Multi-Tenant REST APIs
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Super-admin login; returns Bearer JWT token |
| `POST` | `/api/auth/api-keys` | Generate/regenerate API keys for tenant clients |
| `GET` | `/api/businesses` | List all businesses with active configs, virtual numbers, and hours |
| `POST` | `/api/businesses` | Register a new business with nested config and DIDs |
| `GET` | `/api/businesses/{id}/knowledge` | Retrieve FAQ knowledge base entries for a business |
| `POST` | `/api/businesses/{id}/knowledge` | Add a FAQ entry with category and priority |
| `GET` | `/api/analytics/overview` | Platform-wide KPIs (clients, businesses, calls, leads, bookings) |
| `GET` | `/api/analytics/calls` | Tenant-scoped historical call analytics and duration metrics |

### Telephony & Streaming
| Protocol | Endpoint | Description |
| :--- | :--- | :--- |
| `WS` | `/telephony/media-stream` | Exotel/Twilio Bi-directional Audio WebSocket |
| `POST` | `/telephony/call` | Trigger outbound phone call via Exotel or Twilio |
| `POST` | `/telephony/exotel/status` | Exotel Call Status Webhook Callback |
| `POST` | `/telephony/inbound` | Twilio Inbound Voice Webhook |

---

## ☁️ Deployment

### Option 1: Render (Cloud Backend)

1. Connect your GitHub repository to [Render](https://dashboard.render.com).
2. Create a new **Web Service**:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && pip install -e .`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
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

The project includes `vercel.json` and `api/index.py` configured for deployment on [Vercel](https://vercel.com). Pushing to `main` automatically triggers deployment.

---

## 🔒 Responsible AI Calling & Compliance

- **AI Disclosure**: Clearly informs callers of the agent identity on every turn.
- **DND & Consent**: Supports DND scrubbing and opt-out workflows compliant with TRAI / Indian telecom guidelines.
- **Secure Handling**: Audio streams and credentials are strictly isolated and never stored unencrypted.

---

## 📄 License

MIT License © 2026 SK Voice Agents.
