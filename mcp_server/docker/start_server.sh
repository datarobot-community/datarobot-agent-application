#!/usr/bin/env bash


if [ -z "$DATAROBOT_ENDPOINT" ]; then
    echo "Error: DATAROBOT_ENDPOINT environment variable is required"
    exit 1
fi

# Start the MCP server
echo "Starting MCP server..."
python -m app.main
