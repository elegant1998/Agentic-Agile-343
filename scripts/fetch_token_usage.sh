#!/usr/bin/env sh
# Unix convenience wrapper; token probing is implemented in Python.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/token_usage.py" "$@"
