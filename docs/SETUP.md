# Setup Guide

This guide walks you through setting up Google Cloud and getting your Maps API key.

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

Edit `.env`:
```bash
GOOGLE_MAPS_API_KEY=AIzaSy...your_actual_key_here...

# Generate these with: python -c "import secrets; print(secrets.token_hex(32))"
BACKEND_API_KEY=your_random_32_char_secret
WEBUI_SECRET_KEY=your_random_32_char_secret
```

---

## Step 8: Start the Project

```bash
# Build and start all services
docker compose up -d

# Watch logs (optional)
docker compose logs -f

# Check status
docker compose ps
```

Services:
| Service | URL | Description |
|---------|-----|-------------|
| Open WebUI | http://localhost:3000 | Chat interface |
| FastAPI Backend | http://localhost:8000 | Maps API proxy |
| Ollama | http://localhost:11434 | LLM runtime |
| Redis | localhost:6379 | Cache |

---

## Step 9: Install Tools in Open WebUI

1. Open `http://localhost:3000`
2. Create admin account (first run only)
3. Go to **Workspace → Tools → +**
4. Install each tool from `openwebui-tools/`:

**Tool 1: Google Maps Search**
- Copy content of `openwebui-tools/google_maps_search.py`
- Paste in tool editor → Save

**Tool 2: Google Maps Directions**
- Copy content of `openwebui-tools/google_maps_directions.py`
- Paste → Save

**Tool 3: Google Maps Explorer**
- Copy content of `openwebui-tools/google_maps_explore.py`
- Paste → Save

5. For each tool, click **Edit → Valves** and configure:
   - `backend_url`: `http://backend:8000`
   - `backend_api_key`: (value from your `.env` BACKEND_API_KEY)
   - `google_maps_api_key`: (value from your `.env` GOOGLE_MAPS_API_KEY)

---

## Step 10: Test It!

1. Start a new chat
2. Select model: **qwen3.5:4b**
3. Enable tools: click the tools icon → enable all 3 Maps tools
4. Try these prompts:

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

## Troubleshooting

### Ollama model download stuck
```bash
docker compose logs ollama-pull
# If stuck, manually pull:
docker exec -it heypico-ollama ollama pull qwen3.5:4b
```

### Backend not starting
```bash
docker compose logs backend
# Usually missing GOOGLE_MAPS_API_KEY in .env
```

### Maps not showing in chat
- Make sure you configured **Valves** for each tool with your API key
- Check Static Maps API and Maps Embed API are enabled in Google Cloud

### LLM not calling tools
- Make sure tools are **enabled** in the chat (click tools icon)
- Try a more explicit prompt: *"Use the maps tool to find pizza near me"*
- Qwen 3.5 has good tool-calling — it should detect intent automatically

---

## Monitoring API Usage

Check your Google Maps API usage at:
- [Google Cloud Console → APIs & Services → Dashboard](https://console.cloud.google.com/apis/dashboard)

Watch for:
- Places API (New): charged per request
- Directions API: charged per request  
- Caching in this project significantly reduces API calls for repeated searches
