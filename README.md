# HeyPico Maps LLM 🗺️

A local LLM system that responds to natural language queries about places (restaurants, cafes, attractions, etc.) and displays **interactive embedded Google Maps** directly in the chat.

**Built for HeyPico.ai Code Test 2**

---

## Demo

Ask the LLM things like:
- *"Where can I eat good sushi near SCBD Jakarta?"*
- *"How do I get from Monas to Sarinah?"*
- *"Explore cafes in Bandung Old Town"*
- *"Find tourist attractions near Seminyak Bali"*

The LLM detects the intent, calls the appropriate Google Maps tool via **native function calling**, and returns an **interactive map + place cards / directions** embedded right in the chat.

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                   Open WebUI (port 3000)                  │
│  Chat UI → HeyPico Maps model (qwen2.5:7b via Ollama)    │
│             ↕ native function calling                     │
│           3 Tools → HTMLResponse → embedded map iframes   │
└───────────────────────────────────────────────────────────┘
           ↕ (internal, API-key protected)
┌───────────────────────────────────────────────────────────┐
│              FastAPI Backend (port 8000)                   │
│  • Google Maps API Proxy (API key never exposed to LLM)   │
│  • Rate Limiting (SlowAPI)                                │
│  • Response Caching (Redis)                               │
│  • Input Sanitization                                     │
└───────────────────────────────────────────────────────────┘
           ↕
┌───────────────────────────────────────────────────────────┐
│                   Google Maps APIs                        │
│  • Places API (New) — search places                       │
│  • Directions API — turn-by-turn routes                   │
│  • Geocoding API — address → coordinates                  │
│  • Maps Embed API — interactive iframe                    │
│  • Static Maps API — overview images                      │
└───────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A Google Cloud account with Maps APIs enabled (see [SETUP.md](docs/SETUP.md))
- NVIDIA GPU recommended (runs on CPU too, just slower)
- ~8GB free disk space (for Ollama model + Docker images)

### 2. Clone & Configure

```bash
git clone https://github.com/asd412id/heypico-maps-llm.git
cd heypico-maps-llm

# Copy environment template
cp .env.example .env

# Edit .env and add your keys
# Required: GOOGLE_MAPS_API_KEY, BACKEND_API_KEY, WEBUI_SECRET_KEY
nano .env   # or open in your text editor
```

Generate secret keys:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Start Everything

```bash
docker compose up -d
```

This will automatically:
1. Start Ollama and pull **Qwen 2.5 7B** model (~4.7 GB)
2. Start Redis (cache layer)
3. Start FastAPI backend (Google Maps proxy)
4. Start Open WebUI on port 3000
5. **Auto-register** all 3 Google Maps tools
6. **Auto-configure** tool valves (API keys, backend URL)
7. **Auto-create** `heypico-maps` model with native tool calling enabled

**First run takes 5-10 minutes** while the model downloads. No manual UI setup required.

### 4. Start Chatting

Open `http://localhost:3000` and the `heypico-maps` model is pre-selected. Just type your query! 🎉

---

## Fully Automated Setup

The setup is **100% automated** — no manual steps in the Open WebUI UI:

| What | How |
|------|-----|
| Admin account | Created automatically via API (`admin@heypico.ai`) |
| 3 Google Maps tools | Registered via `setup/setup-tools.py` on first boot |
| Tool valves (API keys) | Configured automatically from `.env` values |
| `heypico-maps` model | Created with `function_calling: native` + all 3 tools attached |
| Default model | `heypico-maps` auto-selected for new chats |

The automation runs inside the Open WebUI container via `setup/entrypoint.sh` → `setup/setup-tools.py`.

For manual re-registration (outside Docker), use:
```bash
python register-tools.py
```

---

## API Endpoints

The backend exposes these endpoints (secured by API key):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/health/maps` | Maps API connectivity check |
| POST | `/maps/search` | Search for places |
| POST | `/maps/directions` | Get directions between two locations |
| POST | `/maps/geocode` | Convert address to coordinates |
| POST | `/maps/explore` | Explore an area by category |

Docs available at `http://localhost:8000/docs` (only when `DEBUG=true`).

---

## Security

- **API key never exposed** — The Google Maps API key lives only in the backend `.env` file. It never reaches the LLM context.
- **Internal authentication** — Tools authenticate to backend using `X-API-Key` header with a separate `BACKEND_API_KEY`.
- **Rate limiting** — Configurable per-minute and per-day limits prevent quota abuse.
- **Input sanitization** — All LLM-generated queries are sanitized before hitting Google APIs.
- **CORS restriction** — Backend only accepts requests from known origins (Open WebUI).
- **Redis caching** — Identical queries are cached (1h for places, 30m for directions, 24h for geocode) to minimize API calls.

---

## Project Structure

```
heypico-maps-llm/
├── docker-compose.yml          # All services orchestration
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
├── register-tools.py           # Standalone tool registration script
│
├── backend/                    # FastAPI backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # App entry point + CORS + rate limiting
│   ├── config.py               # Settings from .env
│   ├── routers/
│   │   ├── maps.py             # Maps API endpoints
│   │   └── health.py           # Health checks
│   ├── services/
│   │   ├── google_maps.py      # Google Maps API client
│   │   └── cache.py            # Redis + in-memory cache
│   ├── middleware/
│   │   ├── security.py         # API key auth + input sanitization
│   │   └── rate_limiter.py     # Rate limiting
│   └── models/
│       └── schemas.py          # Pydantic request/response models
│
├── openwebui-tools/            # Open WebUI Custom Tools
│   ├── google_maps_search.py   # Tool: Search places → HTMLResponse
│   ├── google_maps_directions.py # Tool: Directions → HTMLResponse
│   └── google_maps_explore.py  # Tool: Explore area → HTMLResponse
│
├── setup/                      # Auto-setup (runs on first boot)
│   ├── entrypoint.sh           # Entrypoint wrapper for Open WebUI
│   └── setup-tools.py          # Tool registration + model creation
│
└── docs/
    ├── SETUP.md                # Google Cloud setup guide
    └── ASSUMPTIONS.md          # Documented assumptions & design decisions
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen 2.5 7B (via Ollama) |
| Tool Calling | Native function calling (`function_calling: native`) |
| LLM UI | Open WebUI |
| Tool Output | HTMLResponse → rendered as iframe in chat |
| Backend API | Python FastAPI |
| Cache | Redis 7 |
| Maps | Google Maps Platform (Places API New, Directions, Geocoding, Static Maps, Embed) |
| Containerization | Docker Compose (4 services) |
| Rate Limiting | SlowAPI |

---

## Troubleshooting

**Model not responding to maps queries:**
→ Make sure the `heypico-maps` model is selected in the chat dropdown. It has tools pre-attached with `function_calling: native`.

**"Invalid API key" errors:**
→ Check your `.env` has correct `GOOGLE_MAPS_API_KEY` and `BACKEND_API_KEY`.

**Map images not showing:**
→ Your Google Maps API key must have **Static Maps API** and **Maps Embed API** enabled.

**Docker GPU error:**
→ Remove the `deploy.resources.reservations` block from `docker-compose.yml` if you don't have an NVIDIA GPU. The model runs on CPU (slower but functional).

**Tools not auto-registered:**
→ Check logs: `docker compose logs open-webui | grep setup`. If the setup script timed out, run `python register-tools.py` manually.

---

*Submitted for HeyPico.ai Full Stack Developer Technical Test — Code Test 2*
