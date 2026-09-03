#!/bin/sh
# Entrypoint for the Workload API C2W scenario, invoked with the application root
# as the working directory (see infra/*_infra/workload.py).
# Not used by the Custom Models path.
#
# The agent package is not installed in this image and cannot be: the build
# installs dependencies only, and the application root is read-only at run time.
# It does not need to be. The source is here, and so is the .dist-info holding the
# entry point NAT resolves the workflow through -- the infra program generates it
# from pyproject.toml before uploading. All that is missing is sys.path: `nat` is a
# console script, so the working directory is not on it.
set -eu

export PYTHONPATH="${PWD}${PYTHONPATH:+:${PYTHONPATH}}"

# HOME points at the image user's home directory, which this container, running
# as a different user, cannot write to. Any library that keeps state or caches
# under the home directory fails as a result; CrewAI's memory storage is one.
# Redirect HOME to a writable location.
export HOME="${TMPDIR:-/tmp}/agent-home"
mkdir -p "$HOME"

echo "Running nat dragent serve"
exec nat dragent serve --config_file workflow.yaml --host 0.0.0.0 --port "${WORKLOAD_CONTAINER_PORT:-8080}" --use_gunicorn true
