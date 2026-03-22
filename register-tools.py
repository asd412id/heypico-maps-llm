#!/usr/bin/env python3
"""
Standalone tool registration script for Open WebUI.
Use this to manually register/update tools from outside the container.

Usage:
    python register-tools.py [email] [password]

    Defaults to ADMIN_EMAIL/ADMIN_PASSWORD from .env if not provided.
    Reads API keys from .env or environment variables.
"""

import json
import urllib.request
import urllib.error
import glob
import os
import sys


# Load from .env file if it exists
def load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

WEBUI_URL = os.getenv("WEBUI_URL", "http://localhost:3000/api/v1")
EMAIL = (
    sys.argv[1] if len(sys.argv) > 1 else os.getenv("ADMIN_EMAIL", "admin@heypico.ai")
)
PASSWORD = (
    sys.argv[2] if len(sys.argv) > 2 else os.getenv("ADMIN_PASSWORD", "heypico2026")
)
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "openwebui-tools")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def api(path, data, token=None, method="POST"):
    """Make an API request to Open WebUI."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{WEBUI_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"_error": e.code, "_body": body[:300]}


def main():
    if not BACKEND_API_KEY or not GOOGLE_MAPS_API_KEY:
        print("WARNING: BACKEND_API_KEY or GOOGLE_MAPS_API_KEY not set.")
        print("Valve configuration may fail. Set them in .env or environment.")

    # Login
    print(f"Signing in as {EMAIL}...")
    r = api("/auths/signin", {"email": EMAIL, "password": PASSWORD})
    token = r.get("token")
    if not token:
        print(f"Login failed: {r}")
        sys.exit(1)
    print(f"Logged in as {r.get('name')} ({r.get('role')})")

    # Check existing tools
    existing = []
    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/tools/",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        existing = [t["id"] for t in json.loads(resp.read())]
    except Exception:
        pass
    print(f"Existing tools: {existing}")

    # Register tools
    for filepath in sorted(glob.glob(os.path.join(TOOLS_DIR, "*.py"))):
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

        tool_data = {
            "id": tool_id,
            "name": name,
            "description": desc,
            "content": content,
            "meta": {"description": desc},
        }

        if tool_id in existing:
            # Delete and recreate for clean update
            print(f"Updating: {name}...")
            api(f"/tools/id/{tool_id}/delete", {}, token, method="DELETE")
        else:
            print(f"Creating: {name}...")

        r = api("/tools/create", tool_data, token)
        if "_error" in r:
            print(f"  FAILED: {r['_error']} {r['_body'][:200]}")
            continue

        print(f"  OK: {r.get('id')}")

        # Configure Valves
        valves = {
            "backend_url": BACKEND_URL,
            "frontend_url": FRONTEND_URL,
            "backend_api_key": BACKEND_API_KEY,
            "google_maps_api_key": GOOGLE_MAPS_API_KEY,
        }
        if "search" in tool_id:
            valves["default_radius_meters"] = 5000

        vr = api(f"/tools/id/{tool_id}/valves/update", valves, token)
        if "_error" in vr:
            print(f"  Valves: FAILED {vr['_error']} {vr['_body'][:100]}")
        else:
            print("  Valves: configured")

    # Set heypico-maps as default model
    print("\nSetting default model to heypico-maps...")
    r = api(
        "/configs/models",
        {
            "DEFAULT_MODELS": "heypico-maps",
            "DEFAULT_PINNED_MODELS": "",
            "MODEL_ORDER_LIST": [],
            "DEFAULT_MODEL_METADATA": {},
            "DEFAULT_MODEL_PARAMS": {},
        },
        token,
    )
    if "_error" in r:
        print(f"  FAILED: {r['_error']} {r.get('_body', '')[:200]}")
    else:
        print(f"  OK: default model = {r.get('DEFAULT_MODELS')}")

    print("\nDone!")


if __name__ == "__main__":
    main()
