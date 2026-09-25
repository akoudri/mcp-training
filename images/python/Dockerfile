FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-hashes --all-groups -o /tmp/exigences.txt \
 && uv pip install --system -r /tmp/exigences.txt \
 && rm /tmp/exigences.txt
ENV PYTHONPATH=/app/src:/app \
    PYTHONUNBUFFERED=1 \
    PHAROS_DOCUMENTS=/app/donnees/documents
