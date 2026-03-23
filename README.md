# HeyPico Maps LLM 🗺️

A local LLM system that responds to natural language queries about places (restaurants, cafes, attractions, etc.) and displays **interactive embedded Google Maps** directly in the chat.

**Built for HeyPico.ai Code Test 2**

---

## Demo

Ask the LLM things like:
- *"Where can I eat good sushi near SCBD Jakarta?"*
- *"Find restaurants near me"* (GPS-based nearby search)
- *"How do I get from Monas to Sarinah?"*
- *"Explore cafes in Bandung Old Town"*
- *"Find tourist attractions near Seminyak Bali"*

The LLM detects the intent, calls the appropriate Google Maps tool via **native function calling**, and returns a **static map image** with numbered markers right in the chat, along with a rich info card and clickable Google Maps links (works on mobile; see [Known Limitations](#known-limitations)).

It also supports **"near me" queries** — when the user asks about nearby places, the system detects their location via **browser GPS geolocation** (with IP fallback) and searches around their precise coordinates.

---

## Architecture

```
Browser
  └── http://localhost:3000
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Nginx (port 3000)                           │
│           Single public entry point                          │
│  /api/maps/*  ──────────────────────► backend:8000/maps/*   │
│  /*           ──────────────────────► open-webui:8080        │
└─────────────────────────────────────────────────────────────┘
          │                                      │
          ▼                                      ▼
┌─────────────────────┐              ┌──────────────────────────┐
│ Open WebUI :8080    │              │ FastAPI Backend :8000     │
│ Chat UI             │              │ Google Maps API Proxy     │
│ HeyPico Maps model  │              │ • Rate Limiting           │
│ (qwen2.5:7b)        │              │ • Response Caching        │
│ 4 custom tools      │              │ • Input Sanitization      │
│ native tool calling │              │ • /maps/embed  (public)   │
└─────────────────────┘              │ • /maps/open   (public)   │
          │                          └──────────────────────────┘
          │ (internal, API-key protected)          │
          └─────────────────────────────────────┐  │
                                                 ▼  ▼
                                    ┌──────────────────────────┐
                                    │    Google Maps APIs       │
                                    │ • Places API (New)        │
                                    │ • Directions API          │
                                    │ • Geocoding API           │
                                    │ • Maps Embed API          │
                                    └──────────────────────────┘
```

### How tool results are displayed

```
LLM calls tool
    │
    ▼
Tool calls backend /maps/search|directions|explore (internal, API-key protected)
    │
    ▼
Tool emits type:"embeds" event  ──► Open WebUI renders iframe
    │                                  src = localhost:3000/api/maps/embed?url=...
    │                                  (nginx → backend → HTML wrapper page)
    ▼
Tool returns markdown text to LLM (place list with clickable Google Maps links)
    │
    ▼
LLM presents map + place list in chat
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
nano .env   # or open in your text editor
```

Required values in `.env`:
```bash
GOOGLE_MAPS_API_KEY=AIzaSy...your_actual_key_here...

# Generate these with: python -c "import secrets; print(secrets.token_hex(32))"
BACKEND_API_KEY=your_random_secret
WEBUI_SECRET_KEY=your_random_secret

# Public URL for browser-facing map embed/redirect links (default: http://localhost:3000)
FRONTEND_URL=http://localhost:3000
```

### 3. Start Everything

```bash
docker compose up -d
```

This will automatically:
1. Start Ollama and pull **Qwen 2.5 7B** model (~4.7 GB)
2. Start Redis (cache layer)
3. Start FastAPI backend (Google Maps proxy)
4. Start Open WebUI
5. Start **Nginx** (single public entry point on port 3000)
6. **Auto-register** all 4 Google Maps tools (including GPS location detection)
7. **Auto-configure** tool valves (API keys, backend URL, frontend URL)
8. **Auto-create** `heypico-maps` model with native tool calling enabled

**First run takes 5-10 minutes** while the model downloads. No manual UI setup required.

### 4. Start Chatting

Open `http://localhost:3000` and the `heypico-maps` model is pre-selected. Just type your query! 🎉

---

## Fully Automated Setup

The setup is **100% automated** — no manual steps in the Open WebUI UI:

| What | How |
|------|-----|
| Admin account | Created automatically via API (`admin@heypico.ai`) |
| 4 Google Maps tools | Registered via `setup/setup-tools.py` on first boot |
| Tool valves (API keys) | Configured automatically from `.env` values |
| `heypico-maps` model | Created with `function_calling: native` + all 4 tools attached |
| Default model | `heypico-maps` auto-selected for new chats |

The automation runs inside the Open WebUI container via `setup/entrypoint.sh` → `setup/setup-tools.py`.

For manual re-registration (outside Docker), use:
```bash
python register-tools.py
```

---

## API Endpoints

### Public endpoints (no API key — accessed from browser via nginx)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/maps/embed?url=...&height=450` | HTML wrapper for Google Maps iframe with postMessage auto-resize |
| GET | `/api/maps/open?url=...` | Redirect page that bypasses COOP to open Google Maps in new tab |
| GET | `/api/maps/user-location/card/{user_id}` | Geolocation card with "Allow Location" button |
| GET | `/api/maps/user-location/gps/{user_id}` | GPS popup for browser geolocation detection |
| POST | `/api/maps/geo-result` | Store GPS result from popup (used by geolocation flow) |
| GET | `/api/maps/geo-result/{request_id}` | Poll for GPS result (used by geolocation flow) |

### Internal endpoints (require `X-API-Key` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/health/maps` | Maps API connectivity check |
| POST | `/maps/search` | Search for places |
| POST | `/maps/directions` | Get directions between two locations |
| POST | `/maps/geocode` | Convert address to coordinates |
| POST | `/maps/explore` | Explore an area by category |

> Internal endpoints are called server-side (tool → backend over Docker network). They are not accessible from the browser because the backend has no public port — only nginx can reach it.

Docs available at `http://localhost:8000/docs` (only when `DEBUG=true`).

---

## Security

- **API key never exposed** — The Google Maps API key lives only in the backend `.env` file. It never reaches the LLM context.
- **Internal authentication** — Tools authenticate to backend using `X-API-Key` header with a separate `BACKEND_API_KEY`.
- **No public backend port** — The FastAPI backend is only accessible via nginx (`/api/maps/*`) or internally over the Docker network. Direct access to `:8000` is not possible.
- **Rate limiting** — Configurable per-minute and per-day limits prevent quota abuse.
- **Input sanitization** — All LLM-generated queries are sanitized before hitting Google APIs.
- **CORS restriction** — Backend only accepts requests from known origins (Open WebUI).
- **Redis caching** — Identical queries are cached (1h for places, 30m for directions, 24h for geocode) to minimize API calls.

---

## Project Structure

```
heypico-maps-llm/
├── docker-compose.yml          # All services orchestration (5 services)
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
├── register-tools.py           # Standalone tool registration script
│
├── nginx/
│   └── nginx.conf              # Reverse proxy config (port 3000 entry point)
│
├── backend/                    # FastAPI backend (internal, no public port)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # App entry point + CORS + rate limiting
│   ├── config.py               # Settings from .env
│   ├── routers/
│   │   ├── maps.py             # Maps API + /embed + /open endpoints
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
│   ├── detect_location.py      # Tool: Detect user's GPS location (with IP fallback)
│   ├── google_maps_search.py   # Tool: Search places
│   ├── google_maps_directions.py # Tool: Directions
│   └── google_maps_explore.py  # Tool: Explore area by category
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
| Tool Output | `type:"embeds"` event emitter (iframe) + markdown text |
| Backend API | Python FastAPI |
| Reverse Proxy | Nginx (single public entry point) |
| Cache | Redis 7 |
| Maps | Google Maps Platform (Places API New, Directions, Geocoding, Static Maps) |
| GPS Location | Browser Geolocation API (popup-based, with IP fallback) |
| Containerization | Docker Compose (5 services) |
| Rate Limiting | SlowAPI |

---

## Services

| Service | Internal Port | Public Access | Description |
|---------|--------------|---------------|-------------|
| Nginx | 80 | **http://localhost:3000** | Single entry point (reverse proxy) |
| Open WebUI | 8080 | via nginx | Chat interface |
| FastAPI Backend | 8000 | via nginx `/api/maps/*` | Maps API proxy |
| Ollama | 11434 | internal only | LLM runtime |
| Redis | 6379 | internal only | Response cache |

---

## Troubleshooting

**Model not responding to maps queries:**
→ Make sure the `heypico-maps` model is selected in the chat dropdown. It has tools pre-attached with `function_calling: native`.

**"Invalid API key" errors:**
→ Check your `.env` has correct `GOOGLE_MAPS_API_KEY` and `BACKEND_API_KEY`.

**Map not showing (blocked/error icon):**
→ Verify **Maps Embed API** is enabled in Google Cloud Console. The API key must be allowed for your domain/localhost.

**Google Maps links in place cards don't work on desktop:**
→ This is a known limitation. Open WebUI renders embeds in sandboxed iframes without `allow-popups`, which blocks links on desktop browsers. **Links work on mobile** (opens Google Maps app). On desktop, use the Google Maps links in the text response instead.

**Docker GPU error:**
→ Remove the `deploy.resources.reservations` block from `docker-compose.yml` if you don't have an NVIDIA GPU. The model runs on CPU (slower but functional).

**Tools not auto-registered:**
→ Check logs: `docker compose logs open-webui | grep setup`. If the setup script timed out, run `python register-tools.py` manually.

**`FRONTEND_URL` wrong (embed links broken):**
→ If deployed on a server, set `FRONTEND_URL=https://your-domain.com` in `.env` so embed/redirect URLs use the correct public URL.

---

## Known Limitations

| Limitation | Explanation | Workaround |
|------------|-------------|------------|
| **Google Maps links don't open on desktop** | Open WebUI renders tool embeds inside sandboxed iframes without `allow-popups`. Desktop browsers block `<a target="_blank">` inside these iframes. | On desktop, use the Google Maps links in the LLM's text response (markdown links work normally). |
| **Links work on mobile** | On mobile (Android/iOS), tapping a Maps link in the card triggers the OS intent system, which opens the Google Maps app directly — bypassing the sandbox. | No workaround needed; this is the expected behavior. |
| **Static map images (not interactive)** | Maps use Google Static Maps API images. Zoom/pan is not possible inside the chat. | Click the Google Maps link to open the full interactive map. |

---

*Submitted for HeyPico.ai Full Stack Developer Technical Test — Code Test 2*
