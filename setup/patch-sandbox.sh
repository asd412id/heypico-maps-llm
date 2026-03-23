#!/bin/sh
# Patch Open WebUI iframe sandbox to add allow-popups + geolocation
# This allows:
#   - Links inside embed iframes to open in new tabs (allow-popups)
#   - GPS geolocation from embed iframes (allow attribute)
# Files: compiled Svelte chunks in /app/build/_app/immutable/chunks/
# Idempotent: normalizes first, then patches

echo "[sandbox-patch] Patching iframe sandbox..."

PATCHED=0
for JS_FILE in /app/build/_app/immutable/chunks/*.js; do
    if grep -q 'allow-scripts allow-downloads' "$JS_FILE" 2>/dev/null; then
        # Normalize: remove any flags we manage
        sed -i 's/ allow-popups allow-popups-to-escape-sandbox//g' "$JS_FILE"
        sed -i 's/ allow-same-origin//g' "$JS_FILE"
        # Add allow-popups + allow-same-origin to sandbox attribute
        # allow-same-origin is needed so geolocation permission carries over from parent
        sed -i 's/allow-scripts allow-downloads/allow-scripts allow-downloads allow-same-origin allow-popups allow-popups-to-escape-sandbox/g' "$JS_FILE"
        PATCHED=$((PATCHED + 1))
        echo "[sandbox-patch] Sandbox patched: $(basename $JS_FILE)"
    fi
done

# Patch iframe element to add allow="geolocation" attribute
# This enables navigator.geolocation inside the embed iframe
ALLOW_PATCHED=0
for JS_FILE in /app/build/_app/immutable/chunks/*.js; do
    # Look for the iframe creation pattern and add allow attribute
    if grep -q 'iframe title="Content"' "$JS_FILE" 2>/dev/null; then
        # Only add if not already patched
        if ! grep -q 'allow="geolocation"' "$JS_FILE" 2>/dev/null; then
            sed -i 's/iframe title="Content"/iframe title="Content" allow="geolocation *"/g' "$JS_FILE"
            ALLOW_PATCHED=$((ALLOW_PATCHED + 1))
            echo "[sandbox-patch] Geolocation allow patched: $(basename $JS_FILE)"
        fi
    fi
done

echo "[sandbox-patch] Done. Sandbox: $PATCHED file(s), Geolocation: $ALLOW_PATCHED file(s)."
