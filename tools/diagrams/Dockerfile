# Offline diagrams renderer: Mermaid CLI + Graphviz + Cyrillic fonts + Python tools.
# Pin node image tag in compose.yaml / tools.lock (never :latest).
FROM node:22.14.0-bookworm-slim

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-dejavu-core \
    fonts-noto-core \
    graphviz \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROME_BIN=/usr/bin/chromium

WORKDIR /toolchain
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY requirements.txt ./
RUN python3 -m pip install --break-system-packages -r requirements.txt

WORKDIR /workspace
ENTRYPOINT ["bash", "-lc"]
