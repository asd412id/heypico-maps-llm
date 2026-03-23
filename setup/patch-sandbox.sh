#!/bin/sh
# Patch Open WebUI iframe sandbox to add allow-popups
# This allows links inside embed iframes to open in new tabs
# Files: compiled Svelte chunks in /app/build/_app/immutable/chunks/
# Idempotent: normalizes first, then adds allow-popups

echo "[sandbox-patch] Patching iframe sandbox for allow-popups..."

PATCHED=0
for JS_FILE in /app/build/_app/immutable/chunks/*.js; do
    if grep -q 'allow-scripts allow-downloads' "$JS_FILE" 2>/dev/null; then
        # Normalize: remove any existing allow-popups flags first
        sed -i 's/ allow-popups allow-popups-to-escape-sandbox//g' "$JS_FILE"
        # Add allow-popups flags
        sed -i 's/allow-scripts allow-downloads/allow-scripts allow-downloads allow-popups allow-popups-to-escape-sandbox/g' "$JS_FILE"
        PATCHED=$((PATCHED + 1))
        echo "[sandbox-patch] Patched: $(basename $JS_FILE)"
    fi
done

echo "[sandbox-patch] Done. Patched $PATCHED file(s)."
