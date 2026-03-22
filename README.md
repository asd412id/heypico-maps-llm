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

The LLM detects the intent, calls the appropriate Google Maps tool, and returns an **interactive map + place cards / directions** embedded right in the chat.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Open WebUI (port 3000)                │
│  Chat UI ──▶ Qwen 3.5 4B (via Ollama) ──▶ Maps Tools   │
│                                          ↕               │
│               Rich HTML Maps rendered in chat            │
└─────────────────────────────────────────────────────────┘
           ↕ (internal, API-key protected)
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (port 8000)                 │
│  • Google Maps API Proxy (API key never exposed)         │
│  • Rate Limiting (slowapi)                               │
│  • Response Caching (Redis)                              │
│  • Input Sanitization                                    │
└─────────────────────────────────────────────────────────┘
           ↕
┌─────────────────────────────────────────────────────────┐
│                Google Maps APIs                          │
│  • Places API (New) — search places                      │
│  • Directions API — turn-by-turn routes                  │
│  • Geocoding API — address → coordinates                 │
│  • Maps Embed API — interactive iframe                   │
│  • Static Maps API — overview images                     │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A Google Cloud account with Maps APIs enabled (see [SETUP.md](docs/SETUP.md))
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

This will:
1. Start Ollama (LLM runtime)
2. Automatically pull **Qwen 3.5 4B** model (~3.4 GB)
3. Start Redis (cache)
4. Start FastAPI backend
5. Start Open WebUI on port 3000

**First run takes 5-10 minutes** while the model downloads.

### 4. Install the LLM Tools

Once Open WebUI is running at `http://localhost:3000`:

1. Sign in (create admin account on first run)
2. Go to **Workspace → Tools**
3. Click **"+"** to add a new tool
4. Copy and paste the content of each file from `openwebui-tools/`:
   - `google_maps_search.py`
   - `google_maps_directions.py`
   - `google_maps_explore.py`
5. Save each tool

### 5. Enable Tools for the Model

1. Open a new chat
2. Select **Qwen 3.5 4B** as your model
3. Click the **"+"** or tools icon in the chat bar
4. Enable all 3 Google Maps tools
5. Start chatting! 🎉

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

## Security Best Practices

- **API key never exposed** — The Google Maps API key lives only in the backend `.env` file. It never reaches the browser or LLM context.
- **Internal authentication** — Tools authenticate to backend using `X-API-Key` header with a separate `BACKEND_API_KEY`.
- **Rate limiting** — Configurable per-minute and per-day limits prevent quota abuse.
- **Input sanitization** — All LLM-generated queries are sanitized before hitting Google APIs.
- **CORS restriction** — Backend only accepts requests from known origins (Open WebUI).
- **Redis caching** — Identical queries are cached (1h for places, 30m for directions) to minimize API calls.
- **Restricted API key** — Google Cloud API key should be restricted to specific APIs and HTTP referrers (see SETUP.md).

---

## Project Structure

```
heypico-maps-llm/
├── docker-compose.yml          # All services orchestration
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
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
├── openwebui-tools/            # Open WebUI Custom Tools (Python)
│   ├── google_maps_search.py   # Tool: Search places
│   ├── google_maps_directions.py # Tool: Get directions
│   └── google_maps_explore.py  # Tool: Explore area by category
│
└── docs/
    ├── SETUP.md                # Google Cloud setup guide
    ├── ASSUMPTIONS.md          # Documented assumptions
    └── screenshots/            # Demo screenshots
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen 3.5 4B (via Ollama) |
| LLM UI | Open WebUI |
| Backend API | Python FastAPI |
| Cache | Redis |
| Maps | Google Maps Platform (Places API New, Directions, Geocoding, Static Maps, Embed) |
| Containerization | Docker Compose |
| Rate Limiting | SlowAPI |

---

## Troubleshooting

**Model not responding to maps queries:**
→ Make sure tools are enabled in the chat. Click the tools icon (⚙️ or +) in the chat input.

**"Invalid API key" errors:**
→ Check your `.env` has correct `GOOGLE_MAPS_API_KEY` and `BACKEND_API_KEY`.

**Map images not showing:**
→ Your Google Maps API key must have **Static Maps API** and **Maps Embed API** enabled.

**Docker GPU error:**
→ Remove the `deploy.resources.reservations` block from `docker-compose.yml` if you don't have an NVIDIA GPU. The model runs on CPU (slower but functional).

---

*Submitted for HeyPico.ai Full Stack Developer Technical Test — Code Test 2*
