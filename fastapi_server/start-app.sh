#!/usr/bin/env bash

python3 alembic_migration.py  # migrating base to the last change
uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
