# Base Python devcontainer
FROM mcr.microsoft.com/devcontainers/python:3.12

ENV DR_VERSION=0.5.1

# Install GDB to enable PyCharm -> Attach to Process...
RUN apt update && apt install -y gdb

USER vscode

ENV PATH="/home/vscode/.local/bin:/home/vscode/.pulumi/bin:${PATH}"
ENV PULUMI_SKIP_UPDATE_CHECK=true

# Install uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && uv tool install pre-commit

# Install dr CLI
RUN mkdir -p ~/.local/bin \
    && curl -L -o /tmp/dr.tar.gz \
    https://github.com/datarobot-oss/cli/releases/download/v${DR_VERSION}/dr_v${DR_VERSION}_Linux_x86_64.tar.gz \
    && tar -xzf /tmp/dr.tar.gz -C ~/.local/bin dr \
    && chmod +x ~/.local/bin/dr \
    && rm /tmp/dr.tar.gz

# Install the rest of the template's prerequisites (the pulumi-datarobot plugin, copier, xp)
# from the same versions.yaml the rest of the template checks against, instead of duplicating
# pinned versions and install commands here. uv/task/pulumi must already exist above: dr doesn't
# guarantee an install order, and copier/pulumi-datarobot's own install commands need them.
WORKDIR /workspace
COPY --chown=vscode:vscode .datarobot/cli/versions.yaml .datarobot/cli/versions.yaml
COPY --chown=vscode:vscode .datarobot/cli/scripts .datarobot/cli/scripts
RUN dr dependency install -y

# Verify installations
RUN python --version && uv --version && task --version && pulumi version && dr --version && copier --version && \
    pulumi login --local

ENV SHELL=/bin/bash
