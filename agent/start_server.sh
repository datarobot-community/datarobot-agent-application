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

# When running in a DR deployment, all paths should be mounted below ${URL_PREFIX}/
ROOT_PATH_ARG=""
if [ -n "${URL_PREFIX:-}" ]; then
    ROOT_PATH_ARG="--root_path ${URL_PREFIX}"
fi

# Get the number of workers from the runtime parameter (defaults to 1)
CUSTOM_MODEL_WORKERS=$(python -c "from datarobot.core import getenv; print(int(getenv('CUSTOM_MODEL_WORKERS', '1')))")

echo "Executing command: nat dragent serve --config_file $SCRIPT_DIR/workflow.yaml --port 8080 --use_gunicorn true --workers $CUSTOM_MODEL_WORKERS $ROOT_PATH_ARG"
echo
exec nat dragent serve --config_file $SCRIPT_DIR/workflow.yaml --host 0.0.0.0 --port 8080 --use_gunicorn true --workers $CUSTOM_MODEL_WORKERS $ROOT_PATH_ARG
