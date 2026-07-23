# ── Stage 1: build wheel ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY ovos_busmon/ ./ovos_busmon/
COPY static/ ./static/

RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir /dist


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first (layer cache)
# Install the built wheel
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir --pre /tmp/*.whl && rm /tmp/*.whl

# Copy static UI
COPY --from=builder /build/static /app/static

# Drop to non-root
RUN adduser --disabled-password --gecos '' busmon
USER busmon

EXPOSE 8005

ENV BUSMON_HOST=0.0.0.0
ENV BUSMON_PORT=8005

CMD ["ovos-busmon"]
