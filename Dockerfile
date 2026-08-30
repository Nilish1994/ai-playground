FROM python:3.12.10-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip wheel --wheel-dir /wheels .

FROM debian:bookworm-slim AS bubblewrap-builder
ARG BUBBLEWRAP_VERSION=0.11.2
ARG BUBBLEWRAP_SHA256=69abc30005d2186baf7737feacd8da35633b93cf5af38838ecff17c5f8e924f6
RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates curl gcc libc6-dev libcap-dev meson ninja-build pkg-config xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl --fail --location --silent --show-error \
        "https://github.com/containers/bubblewrap/releases/download/v${BUBBLEWRAP_VERSION}/bubblewrap-${BUBBLEWRAP_VERSION}.tar.xz" \
        --output bubblewrap.tar.xz \
    && echo "${BUBBLEWRAP_SHA256}  bubblewrap.tar.xz" | sha256sum --check \
    && tar --extract --xz --file bubblewrap.tar.xz
RUN meson setup build "bubblewrap-${BUBBLEWRAP_VERSION}" \
        -Dman=disabled -Drequire_userns=false -Dsupport_setuid=true -Dtests=false \
    && meson compile -C build

FROM python:3.12.10-slim AS runtime
RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bubblewrap-builder /src/build/bwrap /usr/bin/bwrap
RUN chown root:root /usr/bin/bwrap && chmod 4755 /usr/bin/bwrap
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/app/.local/bin:$PATH"

RUN groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app
WORKDIR /app
RUN mkdir -p /home/app/.codex && chown -R app:app /home/app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels ai-playground && rm -rf /wheels
COPY alembic.ini ./
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --no-server-header"]
