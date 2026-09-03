#!/usr/bin/env bash

# Custom exec envs (offline demo) keep their own workdir; the stock app base cd's here.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# The offline exec env prepends its notebook-kernel venv to PATH, shadowing the system
# python that DataRobot installed the app deps into. Drop it so python3 (and uvicorn)
# resolve to one interpreter. No-op on the stock app base, where VENV_PATH is unset.
[ -n "${VENV_PATH:-}" ] && PATH="${PATH#"$VENV_PATH/bin:"}"

python3 alembic_migration.py  # migrating base to the last change
uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
