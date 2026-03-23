#!/usr/bin/env python3
"""
Auto-setup script for Open WebUI — runs inside the open-webui container.
1. Create admin account (first user becomes admin)
2. Register all 4 tools (detect_location + 3 Google Maps tools)
3. Configure Valves (API keys, backend URL, frontend URL)
4. Create custom model with native tool calling enabled
5. Configure user settings (location, iframe sandbox, artifacts)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import glob

WEBUI_URL = os.getenv("WEBUI_URL", "http://localhost:8080")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@heypico.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    print("[ERROR] ADMIN_PASSWORD environment variable is required")
    sys.exit(1)
ADMIN_NAME = os.getenv("ADMIN_NAME", "HeyPico Admin")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

BASE_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")
TOOLS_DIR = os.getenv("TOOLS_DIR", "/app/backend/data/tools")


def api(path, data=None, token=None, method="POST"):
    url = f"{WEBUI_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"_error": e.code, "_detail": err[:500]}
    except Exception as e:
        return {"_error": str(e)}


def wait_ready(max_wait=300):
    print("[setup] Waiting for Open WebUI API...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            req = urllib.request.Request(f"{WEBUI_URL}/api/config")
            with urllib.request.urlopen(req, timeout=5):
                print("[setup] Open WebUI API ready")
                return True
        except Exception:
            time.sleep(3)
    print("[setup] Timeout waiting for API")
    return False


def get_token():
    r = api(
        "/api/v1/auths/signup",
        {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "name": ADMIN_NAME,
        },
    )
    if r.get("token"):
        print(f"[setup] Admin created: {ADMIN_EMAIL}")
        return r["token"]

    r = api(
        "/api/v1/auths/signin",
        {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        },
    )
    if r.get("token"):
        print(f"[setup] Signed in: {ADMIN_EMAIL}")
        return r["token"]

    print(f"[setup] Auth failed: {r}")
    return None


def register_tools(token):
    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/api/v1/tools/",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            existing = {t["id"] for t in json.loads(resp.read())}
    except Exception:
        existing = set()

    tools_dir = TOOLS_DIR
    if not os.path.isdir(tools_dir):
        for d in ["/app/setup/../openwebui-tools", "/tools"]:
            if os.path.isdir(d):
                tools_dir = d
                break

    registered = []
    for filepath in sorted(glob.glob(os.path.join(tools_dir, "*.py"))):
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        meta = {}
        if content.startswith('"""'):
            end = content.index('"""', 3)
            for line in content[3:end].strip().split("\n"):
                if ":" in line:
                    k, v = line.strip().split(":", 1)
                    meta[k.strip().lower()] = v.strip()

        tool_id = filename.replace(".py", "")
        name = meta.get("title", filename)
        desc = meta.get("description", "")

        data = {
            "id": tool_id,
            "name": name,
            "description": desc,
            "content": content,
            "meta": {"description": desc},
        }

        if tool_id in existing:
            # Delete and recreate for clean update
            api(f"/api/v1/tools/id/{tool_id}/delete", token=token, method="DELETE")
            r = api("/api/v1/tools/create", data, token)
            action = "updated"
        else:
            r = api("/api/v1/tools/create", data, token)
            action = "created"

        if "_error" not in r:
            print(f"[setup] Tool {action}: {name}")
            registered.append(tool_id)
        else:
            print(
                f"[setup] Tool FAILED ({name}): {r.get('_error')} {r.get('_detail', '')}"
            )

    return registered


def configure_valves(token, tool_ids):
    base_valve_data = {
        "backend_url": BACKEND_URL,
        "backend_api_key": BACKEND_API_KEY,
        "frontend_url": FRONTEND_URL,
    }

    for tool_id in tool_ids:
        valve_data = dict(base_valve_data)
        if "search" in tool_id:
            valve_data["default_radius_meters"] = 5000

        r = api(
            f"/api/v1/tools/id/{tool_id}/valves/update",
            valve_data,
            token,
        )
        if "_error" not in r:
            print(f"[setup] Valves configured: {tool_id}")
        else:
            print(
                f"[setup] Valve FAILED ({tool_id}): {r.get('_error')} {r.get('_detail', '')}"
            )


def configure_user_settings(token):
    """Enable user location, iframe sandbox, and artifact detection for admin user."""
    settings = {
        "userLocation": True,
        "iframeSandboxAllowSameOrigin": True,
        "iframeSandboxAllowForms": True,
        "detectArtifacts": True,
    }
    r = api("/api/v1/users/user/settings/update", settings, token)
    if "_error" not in r:
        print("[setup] User settings configured: location, iframe sandbox, artifacts")
    else:
        print(f"[setup] User settings FAILED: {r.get('_error')} {r.get('_detail', '')}")


def set_default_model(token, model_id="heypico-maps"):
    r = api(
        "/api/v1/configs/models",
        {
            "DEFAULT_MODELS": model_id,
            "DEFAULT_PINNED_MODELS": "",
            "MODEL_ORDER_LIST": [],
            "DEFAULT_MODEL_METADATA": {},
            "DEFAULT_MODEL_PARAMS": {},
        },
        token,
    )
    if "_error" not in r:
        print(f"[setup] Default model set: {model_id}")
    else:
        print(f"[setup] Default model FAILED: {r.get('_error')} {r.get('_detail', '')}")


def create_model(token, tool_ids):
    model_id = "heypico-maps"
    model_data = {
        "id": model_id,
        "name": "HeyPico Maps Assistant",
        "base_model_id": BASE_MODEL,
        "params": {
            "system": (
                "You are HeyPico Maps Assistant — an AI with real-time Google Maps integration.\n\n"
                "CRITICAL RULES:\n"
                "1. For ANY question about places, locations, restaurants, cafes, shops, stores, attractions, hotels, directions, routes, or anything that can be found on a map — you MUST call the Google Maps tools. NEVER answer from memory.\n"
                "2. Available tools: detect_my_location (detect user's current location), search_places (find places), get_directions (route between locations), explore_area (discover places by category).\n"
                "3. NEVER invent or hallucinate place names, addresses, or store names. If a user asks where to find something, use search_places.\n"
                "4. If the user asks in any language, still call the tools — they handle all languages.\n"
                "5. Do NOT say 'I cannot access real-time data' — you CAN, via the tools.\n"
                "6. When the tool returns results, a visual map and info card are ALREADY shown to the user above your message. Do NOT repeat or re-list the details. Just give a brief, friendly summary.\n"
                "7. When the user mentions 'near me', 'nearby', 'terdekat', 'dekat sini', 'sekitar sini', or wants the closest places WITHOUT specifying a location — FIRST call detect_my_location to get their coordinates, THEN pass the latitude and longitude to search_places or explore_area.\n\n"
                "DIRECTIONS RULES:\n"
                '8. For get_directions, the origin and destination MUST be real place names, addresses, or coordinates (e.g. "-6.2,106.8"). NEVER pass "My current location", "my location", "lokasi saya", or similar phrases as origin/destination — the API will reject them.\n'
                '9. If the user wants directions FROM their current location (e.g. "rute dari sini", "dari lokasi saya", "from my location"), you MUST call detect_my_location FIRST, then use the returned latitude,longitude as the origin in get_directions.\n'
                "10. If the user wants directions TO their current location, call detect_my_location FIRST, then use the coordinates as the destination.\n"
                '11. Example flow for \'rute terdekat ke X\': Step 1: call detect_my_location → get coordinates. Step 2: call get_directions(origin="lat,lng", destination="X").'
            ),
            "function_calling": "native",
            "show_tool_results": False,
        },
        "meta": {
            "description": "AI assistant with Google Maps integration — search places, get directions, and explore areas with interactive embedded maps.",
            "toolIds": tool_ids,
        },
    }

    r = api("/api/v1/models/create", model_data, token)
    if "_error" not in r:
        print(f"[setup] Model created: {model_id}")
    else:
        # Model already exists — try update first, then delete+recreate as fallback
        r2 = api("/api/v1/models/model/update", model_data, token)
        if "_error" not in r2:
            print(f"[setup] Model updated: {model_id}")
        else:
            print(
                f"[setup] Update failed ({r2.get('_error')}), trying delete+recreate..."
            )
            api("/api/v1/models/model/delete", {"id": model_id}, token)
            time.sleep(1)
            r3 = api("/api/v1/models/create", model_data, token)
            if "_error" not in r3:
                print(f"[setup] Model recreated: {model_id}")
            else:
                print(
                    f"[setup] Model FAILED: {r3.get('_error')} {r3.get('_detail', '')}"
                )
                return False

    # Ensure params persist via model/update endpoint
    r = api("/api/v1/models/model/update", model_data, token)
    if "_error" not in r:
        print(f"[setup] Model params updated: {model_id}")
    else:
        print(
            f"[setup] Model params update FAILED: {r.get('_error')} {r.get('_detail', '')}"
        )

    return True


def main():
    print("[setup] === HeyPico Auto-Setup ===")

    if not wait_ready():
        sys.exit(0)

    time.sleep(3)

    token = get_token()
    if not token:
        print("[setup] Skipping setup (no auth)")
        sys.exit(0)

    tool_ids = register_tools(token)
    print(f"[setup] {len(tool_ids)} tools registered")

    if tool_ids:
        configure_valves(token, tool_ids)

    all_tools = [
        "detect_location",
        "google_maps_search",
        "google_maps_directions",
        "google_maps_explore",
    ]
    create_model(token, all_tools)
    set_default_model(token, "heypico-maps")
    configure_user_settings(token)

    print(f"[setup] === Setup Complete ===")
    print(f"[setup] Admin: {ADMIN_EMAIL}")
    print(f"[setup] Model: heypico-maps (base: {BASE_MODEL})")
    print(f"[setup] Tools: {', '.join(all_tools)}")


if __name__ == "__main__":
    main()
