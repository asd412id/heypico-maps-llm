# Documented Assumptions

This document explains the key design decisions and assumptions made during the implementation of the HeyPico Maps LLM project.

---

## 1. LLM Model: Qwen 3.5 4B

**Assumption:** Using Qwen 3.5 4B via Ollama as the local LLM.

**Reasoning:**
- Qwen 3.5 is the latest generation (released 2 weeks ago as of writing)
- Has **native tool calling** support (tagged `tools` on Ollama registry)
- 3.4GB size — runs on most laptops with 8GB+ RAM
- 256K context window — excellent for long conversations
- Supports vision + text (multimodal)
- **Qwen 3.5 vs Llama 3.1 8B**: Qwen 3.5 4B has comparable or better tool-calling performance at half the size

**Alternative:** If your machine has 8GB+ VRAM, use `qwen3.5:9b` (6.6GB) for better accuracy.

---

## 2. Open WebUI Custom Tools (Not MCP)

**Assumption:** Using Open WebUI's built-in "Tools" feature (Python plugins) instead of MCP servers or external tool APIs.

**Reasoning:**
- Open WebUI Tools run as Python on the Open WebUI server — no extra infrastructure
- Tools can return `HTMLResponse` that Open WebUI renders as interactive iframes in chat
- This enables **embedded Google Maps directly in chat** — the core UX requirement
- MCP would require an additional server and more complex setup
- Tools integrate natively with Qwen 3.5's tool-calling capability

---

## 3. Backend Proxy Pattern (Security-First)

**Assumption:** The Google Maps API key is NEVER passed to the LLM or browser. All Maps API calls go through the FastAPI backend proxy.

**Reasoning:**
- If the API key were in the Open WebUI tool configuration, it could be exposed in logs, browser DevTools, or prompt injection attacks
- The proxy pattern is a security best practice for third-party API keys
- The backend uses a separate `BACKEND_API_KEY` to authenticate requests from the tools
- This follows the principle of least privilege

---

## 4. Google Maps APIs Used

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

## 5. Redis Caching

**Assumption:** Redis is used for caching API responses with these TTLs:

| API | Cache TTL | Reasoning |
|-----|-----------|-----------|
| Places search | 1 hour | Restaurants/places don't change hourly |
| Directions | 30 minutes | Routes are relatively stable |
| Geocoding | 24 hours | Addresses rarely change |

**Fallback:** If Redis is unavailable, the service falls back to in-memory caching (suitable for dev/demo).

---

## 6. Rate Limiting

**Assumption:** Rate limits are set at 60 requests/minute and 1000 requests/day.

**Reasoning:**
- Google Maps free tier gives $200/month credit (~40,000 map loads or ~100,000 geocode requests)
- Conservative limits protect quota
- Limits are configurable via `.env`
- Uses `slowapi` library with IP-based rate limiting (sliding window)

---

## 7. Docker Compose for Local Deployment

**Assumption:** The project uses Docker Compose to run all services locally.

**Reasoning:**
- One-command setup: `docker compose up -d`
- Reproducible environment for reviewers
- Services communicate over Docker network (no port conflicts)
- Easy to add/remove GPU support

---

## 8. No GPU Required

**Assumption:** The project works on CPU-only machines (slower but functional).

**Reasoning:**
- Qwen 3.5 4B can run on 8GB RAM with CPU inference
- GPU support is enabled by default in `docker-compose.yml` but the deploy block can be removed
- Response time: ~2-5s per token on CPU vs ~0.1s on GPU

---

## 9. Tool Output as Rich HTML

**Assumption:** Tools return full HTML pages that Open WebUI renders as iframes in the chat.

**Reasoning:**
- Open WebUI supports `HTMLResponse` return type from tools
- The HTML includes a `postMessage` script to auto-resize the iframe
- This provides a native embedded map experience without any additional plugins
- Maps show: numbered markers, place photos, ratings, open/closed status, price level, Google Maps links

---

## 10. English-First, Multi-Language Input

**Assumption:** The maps tools use English for API responses but accept queries in any language.

**Reasoning:**
- Google Maps APIs return English results by default
- Qwen 3.5 supports 201 languages for input
- User can ask in Bahasa Indonesia or any language; Qwen translates intent and passes it to the tool
- Map results/labels remain in English (standard for travel apps)
