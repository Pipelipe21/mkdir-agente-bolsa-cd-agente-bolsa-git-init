# Imagen del radar para Cloud Run Jobs.
# Etapa 1: instala dependencias con uv (versiones exactas de uv.lock, sin las de desarrollo).
FROM python:3.12-slim-bookworm AS builder
RUN pip install --no-cache-dir uv==0.8.17
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .

# Etapa 2: imagen final liviana, sin uv, con usuario sin privilegios.
FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 radar
WORKDIR /app
COPY --from=builder --chown=radar:radar /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER radar
CMD ["python", "-m", "jobs.radar"]
