#!/usr/bin/env bash

# Custom exec envs (e.g. air-gapped images) keep their own workdir; the stock app base
# cd's here already, so this is a no-op there.
cd "$(dirname "$(readlink -f "$0")")"

# Custom exec envs built on the notebooks stack prepend their kernel venv to PATH,
# shadowing the system python that DataRobot installed the app deps into. If PATH's
# python3 lacks the app deps, drop the venv entry so python3 (and uvicorn) resolve to
# one interpreter. On the stock app base python3 already imports alembic, so PATH is
# never touched.
if [ -n "${VENV_PATH:-}" ] && ! python3 -c 'import alembic' 2>/dev/null; then
    PATH="${PATH#"$VENV_PATH/bin:"}"
fi

python3 alembic_migration.py  # migrating base to the last change
uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
