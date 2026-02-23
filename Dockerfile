FROM debian:bookworm-slim AS base

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git ripgrep jq openssh-client \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ARG USER_NAME=claude
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid ${USER_GID} ${USER_NAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USER_NAME} \
    && mkdir -p /workspace /home/${USER_NAME}/.claude \
    && chown -R ${USER_UID}:${USER_GID} /workspace /home/${USER_NAME}/.claude

USER ${USER_NAME}
WORKDIR /home/${USER_NAME}

RUN echo '{"hasCompletedOnboarding":true}' > /home/${USER_NAME}/.claude/.claude.json
RUN curl -fsSL https://claude.ai/install.sh | bash

ENV PATH="/home/${USER_NAME}/.local/bin:${PATH}" \
    CLAUDE_CONFIG_DIR="/home/${USER_NAME}/.claude" \
    DISABLE_AUTOUPDATER=1 \
    NODE_OPTIONS="--max-old-space-size=4096"

WORKDIR /workspace

FROM base AS minimal
RUN claude --version
CMD ["claude"]

FROM base AS full
USER root
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && npm cache clean --force 2>/dev/null || true
USER claude
RUN claude --version && node --version
CMD ["claude"]