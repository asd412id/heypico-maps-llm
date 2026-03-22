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
- Tools return `HTMLResponse` that Open WebUI renders as interactive iframes in chat
- This enables **embedded Google Maps directly in chat** — the core UX requirement
- MCP would require an additional server and more complex setup
- Tools integrate natively with Qwen's tool-calling capability via `function_calling: native`

---

## 3. HTMLResponse for Rich Map Rendering

**Assumption:** Tools return `HTMLResponse` (from `fastapi.responses`) instead of plain HTML strings.

**Reasoning:**
- Open WebUI's middleware detects `HTMLResponse` return type and auto-renders it as an iframe embed
- Plain string HTML is shown as raw text; `HTMLResponse` triggers the iframe rendering pipeline
- The `Content-Disposition: inline` header ensures proper display
- When a tool returns `HTMLResponse`, Open WebUI replaces the tool result sent to the LLM with a brief "UI active" message, preventing the LLM from seeing raw HTML

---

## 4. Fully Automated Setup (No Manual UI Steps)

**Assumption:** The entire setup — admin account, tool registration, valve configuration, model creation — is automated via API.

**Reasoning:**
- Reviewers should be able to run `docker compose up -d` and have everything working
- `setup/entrypoint.sh` wraps the Open WebUI startup and runs `setup-tools.py` in the background
- `setup-tools.py` handles: admin signup, tool create (delete+recreate pattern), valve configuration, and model creation
- The `heypico-maps` model is created with `function_calling: native` and all 3 tools pre-attached
- `DEFAULT_MODELS=heypico-maps` ensures the model is auto-selected for new chats

---

## 5. Backend Proxy Pattern (Security-First)

**Assumption:** The Google Maps API key is NEVER passed to the LLM or browser. All Maps API calls go through the FastAPI backend proxy.

**Reasoning:**
- If the API key were in the Open WebUI tool configuration, it could be exposed in logs, browser DevTools, or prompt injection attacks
- The proxy pattern is a security best practice for third-party API keys
- The backend uses a separate `BACKEND_API_KEY` to authenticate requests from the tools
- This follows the principle of least privilege

**Note:** The Google Maps API key is still used in `photo_url` and `embed_url` responses (for Static Maps/Embed API), as these URLs are rendered client-side. In production, use a domain-restricted API key for these.

---

## 6. Google Maps APIs Used

**Assumption:** The following APIs are enabled on the Google Cloud project:

| API | Purpose |
|-----|---------|
| Places API (New) | Text search for places (`/places:searchText`) |
| Directions API | Turn-by-turn route calculation |
| Geocoding API | Convert addresses to lat/lng coordinates |
| Maps Embed API | Interactive directions iframe |
| Static Maps API | Overview map images with numbered markers |

**Note:** Places API (New) is used instead of the legacy Places API for future-proof compatibility. It uses field masks for efficient data fetching.

---

## 7. Redis Caching

**Assumption:** Redis is used for caching API responses with these TTLs:

| API | Cache TTL | Reasoning |
|-----|-----------|-----------|
| Places search | 1 hour | Restaurants/places don't change hourly |
| Directions | 30 minutes | Routes are relatively stable |
| Geocoding | 24 hours | Addresses rarely change |

**Fallback:** If Redis is unavailable, the service falls back to in-memory caching (suitable for dev/demo).

---

## 8. Rate Limiting

**Assumption:** Rate limits are set at 60 requests/minute and 1000 requests/day.

**Reasoning:**
- Google Maps free tier gives $200/month credit (~40,000 map loads or ~100,000 geocode requests)
- Conservative limits protect quota
- Limits are configurable via `.env`
- Uses `slowapi` library with IP-based rate limiting (sliding window)

---

## 9. Docker Compose for Local Deployment

**Assumption:** The project uses Docker Compose with 4 services to run everything locally.

**Services:** Ollama (LLM), Redis (cache), Backend (FastAPI), Open WebUI (chat UI + tool orchestrator)

**Reasoning:**
- One-command setup: `docker compose up -d`
- Reproducible environment for reviewers
- Services communicate over Docker network (no port conflicts)
- GPU support enabled by default (can be removed for CPU-only)

---

## 10. Native Tool Calling

**Assumption:** The `heypico-maps` model uses `function_calling: native` (not prompt-based).

**Reasoning:**
- Qwen 2.5 7B supports native tool calling natively
- `native` mode passes tool schemas directly in the model's tool-calling format
- More reliable than prompt-based function calling (which embeds tool schemas in the system prompt)
- Open WebUI's model API supports `params.function_calling: "native"` to enable this

---

## 11. Delete + Recreate Pattern for Tool Updates

**Assumption:** When updating tools, we delete the existing tool and recreate it instead of using PUT/POST update.

**Reasoning:**
- Open WebUI v0.8.10's POST update endpoint for tools returns HTTP 405
- Delete (`DELETE /api/v1/tools/id/{id}/delete`) + Create (`POST /api/v1/tools/create`) works reliably
- This pattern is used in both `setup-tools.py` (container) and `register-tools.py` (standalone)

---

## 12. No GPU Required (But Recommended)

**Assumption:** The project works on CPU-only machines.

**Reasoning:**
- Qwen 2.5 7B can run on CPU with 16GB+ RAM
- GPU support is enabled by default in `docker-compose.yml` (NVIDIA)
- Remove the `deploy.resources.reservations` block for CPU-only machines
- Response time: ~2-5s per token on CPU vs ~0.1s on GPU
