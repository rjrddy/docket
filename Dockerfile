FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build
FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-dev.txt ./
RUN python -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements-dev.txt
COPY src/ src/
COPY scripts/ scripts/
COPY data/ data/
COPY docs/results/*.json docs/results/
COPY --from=web /web/dist apps/web/dist/
RUN useradd -u 10001 -m docket && mkdir -p .cache/documents && chown -R docket:docket /app
USER 10001
ENV PYTHONPATH=src DOCKET_HOST=0.0.0.0 PORT=8096
EXPOSE 8096
CMD [".venv/bin/python", "-m", "docket.server"]
