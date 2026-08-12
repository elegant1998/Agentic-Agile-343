#!/usr/bin/env sh
# Unix compatibility wrapper. The implementation is Python and also runs on Windows.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/telemetry_workflow.py" "$@"
