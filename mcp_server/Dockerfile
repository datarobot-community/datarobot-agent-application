# Copyright 2025 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# User configuration
ARG UID=1000
ARG GID=1000
ARG UNAME=appuser

# Single-stage image: DataRobot remote builds pay for each FROM and cross-stage
# COPY; multi-stage added a second base pull and an extra tree copy/chown without
# helping cache much on ephemeral CI stacks. Keep deps-before-app COPY for layer
# reuse when lockfiles are unchanged.
FROM datarobot/mirror_chainguard_datarobot.com_python-fips:3.12-dev

ARG UID
ARG GID
ARG UNAME

# Root by its numeric uid: hadolint DL3066 requires numeric user ids
USER 0

RUN addgroup -g "$GID" "$UNAME" && \
    adduser -D -u "$UID" -G "$UNAME" -s /bin/sh "$UNAME"

WORKDIR /opt/code
ENV HOME=/opt/code \
    PYTHONPATH=/opt/code \
    PATH="/opt/venv/bin:${PATH}"

# Pin uv by digest (linux/amd64). Update via: docker buildx imagetools inspect ghcr.io/astral-sh/uv:latest
COPY --from=ghcr.io/astral-sh/uv@sha256:21fedfa1151bb363a6cb32e4a34a032e26f02b3e9e288a96f126ac27d3b472d6 /uv /uvx /usr/local/bin/

ENV UV_PROJECT=/opt/code \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Dependencies first — lockfile layer caches when pyproject.toml/uv.lock are unchanged.
# --no-install-project: deps only; app runs via PYTHONPATH (see start_server.sh for pinned EE).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-progress --color never && \
    chown -R "${UID}:${GID}" /opt/venv

# Copy the rest of the build context AFTER the deps layer so app-only changes
# never invalidate the uv sync cache. What lands here depends on the context:
#   - EE builds (context = app root): .dockerignore strips app/ etc., leaving a
#     deps-only image — the platform injects model files at runtime.
#   - Workload DockerfileProvided builds (context = Files catalog bundle, which
#     has no .dockerignore): this copies app/ + start_server.sh, which CMD needs.
#     Without it the container crash-loops on `python -m app.main` (workload
#     status ERRORED).
COPY . .
RUN chown -R "${UID}:${GID}" /opt/code

# DL3066 wants a numeric uid, but this user is a build arg and a variable never
# looks numeric to hadolint — acknowledged rather than hardcoding the id.
# hadolint ignore=DL3066
USER $UNAME

EXPOSE 8080

ENTRYPOINT []

# Same entrypoint as workload DEFAULT_ENTRYPOINT — deps are baked at build time.
CMD ["python", "-m", "app.main"]
