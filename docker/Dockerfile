# syntax=docker/dockerfile:1.12
FROM python:3.13-slim AS base

LABEL org.opencontainers.image.source="https://github.com/marimo-team/marimo"
LABEL org.opencontainers.image.description="marimo reactive notebook"

# Make `uv` and `uvx` available in the PATH for all target images
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/

# Create a non-root user
RUN useradd -m appuser

WORKDIR /app

ARG marimo_version=0.12.8
LABEL org.opencontainers.image.version="${marimo_version}"

ENV MARIMO_SKIP_UPDATE_CHECK=1
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN uv pip install --no-cache-dir marimo==${marimo_version} && \
  mkdir -p /app/data && \
  chown -R appuser:appuser /app && \
  chown -R appuser:appuser /usr/local/lib/python3.13/site-packages/ && \
  chown -R appuser:appuser /usr/local/bin/

COPY --chown=appuser:appuser marimo/_tutorials tutorials
RUN rm -rf tutorials/__init__.py

ENV PORT=8080
EXPOSE $PORT

ENV HOST=0.0.0.0

STOPSIGNAL SIGTERM

# -slim entry point
FROM base AS slim
USER appuser
CMD ["sh", "-c", "exec marimo edit --no-token -p $PORT --host $HOST"]

# -data entry point
FROM base AS data
USER appuser
RUN uv pip install --no-cache-dir \
    altair \
    marimo[recommended,lsp] \
    numpy \
    pandas
CMD ["sh", "-c", "exec marimo edit --no-token -p $PORT --host $HOST"]

# -sql entry point, extends -data
FROM data AS sql
RUN uv pip install --no-cache-dir marimo[sql]
CMD ["sh", "-c", "exec marimo edit --no-token -p $PORT --host $HOST"]
