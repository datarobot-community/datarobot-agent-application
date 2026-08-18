#!/bin/sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Configure UV package manager
export UV_PROJECT="${CODE_DIR:-/opt/code}"
export UV_PROJECT_ENVIRONMENT="${VENV_DIR:-/opt/venv}"
export UV_COMPILE_BYTECODE=0  # Disable compilation
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

# Create venv in code dir.
uv venv "${UV_PROJECT_ENVIRONMENT}"
# shellcheck disable=SC1091
. "${UV_PROJECT_ENVIRONMENT}/bin/activate"

# Sync dependencies using UV
# --active: Install into the active venv instead of creating a new one
# --frozen: Skip dependency resolution, use exact versions from lock file
# Note: Compilation disabled since kernel venv is already compiled
# Does not fail on errors to avoid blocking the startup of the server
uv sync --frozen --active --no-progress --color never || true

# Optional: Dump environment variables for debugging
if [ "${ENABLE_CUSTOM_MODEL_RUNTIME_ENV_DUMP}" = "1" ]; then
    echo "Environment variables:"
    env
fi

echo "Starting Custom Model environment with MCP server"

# Set Python path to script directory for module imports
export PYTHONPATH="$SCRIPT_DIR"

# Start the MCP server
exec python -m app.main
