#!/usr/bin/env bash

# Run from the app source directory. The stock application base env sets its working
# directory there, but a custom execution environment (used for the offline demo) keeps
# its own working directory, so alembic_migration.py and the app package would not be
# found on the relative paths below.
cd "$(dirname "$(readlink -f "$0")")"

# DataRobot installs the app dependencies into the interpreter that runs the app. On the
# stock application base that is what `python3` resolves to, but a custom execution
# environment (the offline demo) prepends its own virtualenv to PATH, and that python
# lacks the app dependencies (e.g. alembic) — so the migration below failed to import
# them. The uvicorn console script's shebang points at the interpreter DataRobot
# installed into; reuse it for the migration. Fall back to python3 if it can't be read.
app_python="$(sed -n '1s/^#!//p' "$(command -v uvicorn)" 2>/dev/null)"
[ -x "$app_python" ] || app_python=python3

"$app_python" alembic_migration.py  # migrating base to the last change
uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --timeout-keep-alive 300
