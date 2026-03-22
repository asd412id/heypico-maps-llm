# Setup Guide

This guide walks you through the one-time Google Cloud setup and deploying the project.

---

## Step 1: Create Google Cloud Account

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Accept the Terms of Service
4. **Get $200/month free credit** for Google Maps APIs automatically

---

## Step 2: Create a New Project

1. Click the project dropdown (top-left) → **New Project**
2. Name it: `heypico-maps-llm`
3. Click **Create**

---

## Step 3: Enable Required APIs

Navigate to **APIs & Services → Library** and enable:

1. **Places API (New)** — search: `Places API`
2. **Directions API** — search: `Directions API`
3. **Geocoding API** — search: `Geocoding API`
4. **Maps Embed API** — search: `Maps Embed API`
5. **Maps Static API** — search: `Maps Static API`

For each:
- Click the API name
- Click **Enable**

---

## Step 4: Create API Key

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → API Key**
3. Copy the generated key — you'll need it for `.env`

---

## Step 5: Restrict the API Key (IMPORTANT for security)

1. Click on your newly created API key to edit it
2. Under **Application restrictions**:
   - For development: Choose **None** (or IP addresses → add `127.0.0.1`)
   - For production: Choose **HTTP referrers** → add your domain
3. Under **API restrictions**:
   - Select **Restrict key**
   - Check only the APIs you enabled:
     - Places API (New)
     - Directions API
     - Geocoding API
     - Maps Embed API
     - Maps Static API
4. Click **Save**

> ⚠️ **Never commit your API key to git.** The `.gitignore` already excludes `.env`.

---

## Step 6: Set Up Budget Alert (Optional but Recommended)

1. Go to **Billing → Budgets & alerts**
2. Create budget: $10/month
3. Set alerts at 50%, 90%, 100%
4. This prevents unexpected charges

---

## Step 7: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — only 3 values need changing:

```bash
GOOGLE_MAPS_API_KEY=AIzaSy...your_actual_key_here...

# Generate these with: python -c "import secrets; print(secrets.token_hex(32))"
BACKEND_API_KEY=your_random_secret
WEBUI_SECRET_KEY=your_random_secret
```

All other values have sensible defaults.

---

## Step 8: Deploy (One Command)

```bash
docker compose up -d
```

**That's it!** Everything is automated:

| Step | What Happens |
|------|-------------|
| 1 | Ollama starts and pulls `qwen2.5:7b` (~4.7 GB) |
| 2 | Redis starts for response caching |
| 3 | FastAPI backend starts with health checks |
| 4 | Open WebUI starts on port 3000 |
| 5 | `setup-tools.py` auto-creates admin account |
| 6 | Auto-registers 3 Google Maps tools + configures valves |
| 7 | Auto-creates `heypico-maps` model with native tool calling |

First run takes **5-10 minutes** (model download). Subsequent starts are ~30 seconds.

Watch the progress:
```bash
docker compose logs -f
```

Check service status:
```bash
docker compose ps
```

---

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Open WebUI | http://localhost:3000 | Chat interface (auto-configured) |
| FastAPI Backend | http://localhost:8000 | Maps API proxy |
| Ollama | http://localhost:11434 | LLM runtime |
| Redis | localhost:6379 | Cache |

---

## Step 9: Start Chatting

Open `http://localhost:3000`. The `heypico-maps` model is automatically selected.

Try these prompts:

```
Where should I eat dinner near SCBD Jakarta?
```

```
How do I get from Monas to Sarinah Mall by walking?
```

```
Explore cafes in Bandung Old Town
```

```
Find tourist attractions near Seminyak Bali
```

---

## Manual Tool Registration (Optional)

If the auto-setup didn't run (e.g., timeout), you can register tools manually from outside Docker:

```bash
python register-tools.py
```

This script reads credentials from `.env` and registers all 3 tools + configures valves via the Open WebUI API.

---

## Troubleshooting

### Ollama model download stuck
```bash
docker compose logs ollama
# If stuck, restart the service:
docker compose restart ollama
```

### Backend not starting
```bash
docker compose logs backend
# Usually missing GOOGLE_MAPS_API_KEY in .env
```

### Maps not showing in chat
- Verify Static Maps API and Maps Embed API are enabled in Google Cloud
- Check tool valves are configured: `docker compose logs open-webui | grep setup`

### LLM not calling tools
- Make sure the `heypico-maps` model is selected (not the base `qwen2.5:7b`)
- The `heypico-maps` model has `function_calling: native` + tools pre-attached
- Try a more explicit prompt: *"Use the maps tool to find pizza near Sudirman Jakarta"*

### Setup script timeout
- If `docker compose logs open-webui | grep "Timeout"`, run `python register-tools.py` manually
- The setup script waits up to 5 minutes for Open WebUI to be ready

---

## Monitoring API Usage

Check your Google Maps API usage at:
- [Google Cloud Console → APIs & Services → Dashboard](https://console.cloud.google.com/apis/dashboard)

Watch for:
- Places API (New): charged per request
- Directions API: charged per request
- Caching significantly reduces API calls for repeated searches
