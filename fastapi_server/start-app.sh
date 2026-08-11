#!/usr/bin/env bash

uv run python3 alembic_migration.py  # migrating base to the last change
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
