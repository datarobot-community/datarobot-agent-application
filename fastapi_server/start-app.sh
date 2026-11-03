#!/usr/bin/env bash

# Custom exec envs (offline demo) keep their own workdir; the stock app base cd's here.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# The offline exec env puts its notebook-kernel venv on PATH, more than once, shadowing
# the system python that DataRobot installed the app deps into. Drop every copy so python3
# (and uvicorn) resolve to one interpreter. No-op on the stock app base, where VENV_PATH is unset.
if [ -n "${VENV_PATH:-}" ]; then
  p=":$PATH:"
  while [[ $p == *":$VENV_PATH/bin:"* ]]; do p="${p//:$VENV_PATH\/bin:/:}"; done
  p="${p#:}"
  PATH="${p%:}"
fi

python3 alembic_migration.py  # migrating base to the last change
uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
