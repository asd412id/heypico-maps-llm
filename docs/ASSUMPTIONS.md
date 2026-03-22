# Documented Assumptions

This document explains the key design decisions and assumptions made during the implementation of the HeyPico Maps LLM project.

---

## 1. LLM Model: Qwen 2.5 7B

**Assumption:** Using Qwen 2.5 7B via Ollama as the local LLM.

**Reasoning:**
- Qwen 2.5 has **excellent native tool calling** support (tagged `tools` on Ollama registry)
- 4.7GB size — fits in 6GB+ VRAM (tested on RTX 3060 Laptop 6GB)
- Strong instruction-following and multi-language support
- **Why not Qwen 3.5 4B?** Tested during development; Qwen 2.5 7B showed more reliable tool calling behavior with `function_calling: native` in Open WebUI

**Alternative:** If your machine has 8GB+ VRAM, use `qwen2.5:14b` for better accuracy.

---

## 2. Open WebUI Custom Tools (Not MCP)

**Assumption:** Using Open WebUI's built-in "Tools" feature (Python plugins) instead of MCP servers.

**Reasoning:**
- Open WebUI Tools run as Python on the Open WebUI server — no extra infrastructure
- Tools emit `type:"embeds"` events that Open WebUI renders as interactive iframes in chat
- Tools return markdown text that the LLM uses to present structured place results
- MCP would require an additional server and more complex setup
- Tools integrate natively with Qwen's tool-calling capability via `function_calling: native`

---

## 3. type:"embeds" + Markdown Text (Not HTMLResponse)

**Assumption:** Tools use `type:"embeds"` event emitter for the map iframe and return markdown text (not `HTMLResponse`).

**Reasoning:**
- `type:"embeds"` is Open WebUI's native embed system — renders the map URL as a sandboxed iframe directly in chat
- Markdown text is passed to the LLM so it can present place names, ratings, and clickable Google Maps links in a natural conversational way
- `HTMLResponse` was found to be unreliable in some Open WebUI versions and is no longer used
- The combination of `embeds` (visual map) + markdown (text list) gives the best UX

---

## 4. Nginx Reverse Proxy (Single Entry Point)

**Assumption:** Nginx sits in front of Open WebUI and the backend as a single public entry point on port 3000.

**Routing:**
```
localhost:3000/api/maps/*  →  backend:8000/maps/*
localhost:3000/*           →  open-webui:8080
```

**Reasoning:**
- The backend has endpoints that must be accessible from the browser (for iframe rendering) without an API key: `/maps/embed` and `/maps/open`
- These must be on the same origin as Open WebUI to avoid CORS issues
- Nginx routes them cleanly without exposing the backend's other internal endpoints
- Open WebUI and the backend have no public ports — all traffic goes through nginx

---

## 5. Two URL Valves: backend_url and frontend_url

**Assumption:** Each tool has two URL valves:

| Valve | Default | Used for |
|-------|---------|----------|
| `backend_url` | `http://backend:8000` | Server-side API calls (tool → backend over Docker network) |
| `frontend_url` | `http://localhost:3000` | Browser-side embed/redirect URLs sent to the user's browser |

**Reasoning:**
- Server-side calls use the internal Docker network hostname (`backend:8000`)
- Browser-side URLs must use the public URL (via nginx) because they are rendered in the user's browser
- Using `backend:8000` in browser-side URLs would fail (user's browser can't reach Docker internal network)
- `FRONTEND_URL` in `.env` sets both valves automatically; change it for production deployments

---

## 6. /maps/embed and /maps/open Endpoints

**Assumption:** Two public (no API key) endpoints are served via nginx → backend:

### `/maps/embed?url=...&height=450`
- Returns an HTML page that wraps the Google Maps embed iframe
- Sends `postMessage({type:'iframe:height', height})` to the Open WebUI parent frame so the embed auto-resizes
- The URL must be a valid `google.com` or `googleapis.com` URL (validated server-side)

### `/maps/open?url=...`
- Returns an HTML page that redirects to a Google Maps URL
- Serves with `Cross-Origin-Opener-Policy: unsafe-none` to break the COOP chain
- Open WebUI sets `COOP: same-origin` on all its pages, which blocks Google Maps from opening normally; this endpoint breaks that chain
- Uses `window.location.replace()` to navigate without creating a popup (no `allow-popups` sandbox permission needed)

---

## 7. Fully Automated Setup (No Manual UI Steps)

**Assumption:** The entire setup — admin account, tool registration, valve configuration, model creation — is automated via API.

**Reasoning:**
- Reviewers should be able to run `docker compose up -d` and have everything working
- `setup/entrypoint.sh` wraps the Open WebUI startup and runs `setup-tools.py` in the background
- `setup-tools.py` handles: admin signup, tool create (delete+recreate pattern), valve configuration, and model creation
- The `heypico-maps` model is created with `function_calling: native` and all 3 tools pre-attached
- `DEFAULT_MODELS=heypico-maps` ensures the model is auto-selected for new chats

---

## 8. Backend Proxy Pattern (Security-First)

**Assumption:** The Google Maps API key is NEVER passed to the LLM or browser. All Maps API calls go through the FastAPI backend proxy.

**Reasoning:**
- If the API key were in the Open WebUI tool configuration, it could be exposed in logs, browser DevTools, or prompt injection attacks
- The proxy pattern is a security best practice for third-party API keys
- The backend uses a separate `BACKEND_API_KEY` to authenticate requests from the tools
- The backend has **no public port** — only nginx and the Docker internal network can reach it

**Note:** The Google Maps API key IS used in `embed_url` responses (for Maps Embed API iframe `src`). This URL is rendered client-side by the browser. In production, use an HTTP-referrer-restricted API key for Maps Embed.

---

## 9. Google Maps APIs Used

**Assumption:** The following APIs are enabled on the Google Cloud project:

| API | Purpose |
|-----|---------|
| Places API (New) | Text search for places (`/places:searchText`) |
| Directions API | Turn-by-turn route calculation |
| Geocoding API | Convert addresses to lat/lng coordinates |
| Maps Embed API | Interactive map iframe in chat |

> **Static Maps API is no longer used.** It was previously used for overview images but has been replaced by the Maps Embed API for a better interactive experience.

**Note:** Places API (New) is used instead of the legacy Places API for future-proof compatibility. It uses field masks for efficient data fetching.

---

## 10. Redis Caching

**Assumption:** Redis is used for caching API responses with these TTLs:

| API | Cache TTL | Reasoning |
|-----|-----------|-----------|
| Places search | 1 hour | Restaurants/places don't change hourly |
| Directions | 30 minutes | Routes are relatively stable |
| Geocoding | 24 hours | Addresses rarely change |

**Fallback:** If Redis is unavailable, the service falls back to in-memory caching (suitable for dev/demo).

---

## 11. Rate Limiting

**Assumption:** Rate limits are set at 60 requests/minute and 1000 requests/day.

**Reasoning:**
- Google Maps free tier gives $200/month credit (~40,000 map loads or ~100,000 geocode requests)
- Conservative limits protect quota
- Limits are configurable via `.env`
- Uses `slowapi` library with IP-based rate limiting (sliding window)

---

## 12. Docker Compose for Local Deployment

**Assumption:** The project uses Docker Compose with **5 services** to run everything locally.

**Services:**
| Service | Role |
|---------|------|
| Nginx | Reverse proxy, single public port 3000 |
| Open WebUI | Chat UI + tool orchestrator |
| Backend (FastAPI) | Google Maps API proxy |
| Ollama | Local LLM runtime |
| Redis | Response cache |

**Reasoning:**
- One-command setup: `docker compose up -d`
- Reproducible environment for reviewers
- Services communicate over Docker network (no port conflicts)
- Nginx as single entry point ensures `/api/maps/*` and Open WebUI share the same origin (no CORS)
- GPU support enabled by default (can be removed for CPU-only)

---

## 13. Native Tool Calling

**Assumption:** The `heypico-maps` model uses `function_calling: native` (not prompt-based).

**Reasoning:**
- Qwen 2.5 7B supports native tool calling natively
- `native` mode passes tool schemas directly in the model's tool-calling format
- More reliable than prompt-based function calling (which embeds tool schemas in the system prompt)
- Open WebUI's model API supports `params.function_calling: "native"` to enable this

---

## 14. Delete + Recreate Pattern for Tool Updates

**Assumption:** When updating tools, we delete the existing tool and recreate it instead of using PUT/POST update.

**Reasoning:**
- Open WebUI v0.8.10's POST update endpoint for tools returns HTTP 405
- Delete (`DELETE /api/v1/tools/id/{id}/delete`) + Create (`POST /api/v1/tools/create`) works reliably
- This pattern is used in both `setup-tools.py` (container) and `register-tools.py` (standalone)

---

## 15. No GPU Required (But Recommended)

**Assumption:** The project works on CPU-only machines.

**Reasoning:**
- Qwen 2.5 7B can run on CPU with 16GB+ RAM
- GPU support is enabled by default in `docker-compose.yml` (NVIDIA)
- Remove the `deploy.resources.reservations` block for CPU-only machines
- Response time: ~2-5s per token on CPU vs ~0.1s on GPU
