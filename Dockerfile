FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv

FROM mirror.gcr.io/library/node:24.21.0-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS node

FROM mirror.gcr.io/library/debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 AS gpgx

ARG GPGX_REF=a5834b3df455c49bb97bfaa328c20845831f576b

RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none --no-checkout https://github.com/ekeeke/Genesis-Plus-GX.git /src/gpgx \
    && git -C /src/gpgx checkout --quiet "${GPGX_REF}" \
    && test "$(git -C /src/gpgx rev-parse HEAD)" = "${GPGX_REF}"

WORKDIR /src/gpgx

RUN make -f Makefile.libretro -j"$(nproc)" \
    && cp genesis_plus_gx_libretro.so /src/genesis_plus_gx_libretro.so

COPY compare/frontend.c /src/frontend.c

RUN gcc -O2 -std=c11 -Wall -Wextra -Werror -o /src/gpgx-frames /src/frontend.c \
        -I/src/gpgx/libretro/libretro-common/include -ldl

FROM mirror.gcr.io/library/python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git make poppler-utils shellcheck \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/corepack /usr/local/lib/node_modules/corepack
COPY --from=gpgx /src/gpgx-frames /usr/local/bin/gpgx-frames
COPY --from=gpgx /src/genesis_plus_gx_libretro.so /usr/local/lib/genesis_plus_gx_libretro.so

ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    COREPACK_HOME=/opt/corepack \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PYGAME_HIDE_SUPPORT_PROMPT=1 \
    SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy \
    PATH=/opt/venv/bin:/opt/tools/node_modules/.bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH=/sega-sms-python:/sega-sms-python/zilog-z80-python:/sega-sms-python/sega-vdp-python:/sega-sms-python/sega-vdp-python/ti-tms9918-python:/sega-sms-python/sega-vdp-python/ti-sn76489-python:/sega-sms-python/sms-mapper-python

WORKDIR /opt/tools

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --only-group dev --only-group play --no-install-project

COPY package.json pnpm-lock.yaml ./
RUN node /usr/local/lib/node_modules/corepack/dist/corepack.js pnpm@11.22.0 install --frozen-lockfile --ignore-scripts \
    && chmod -R a+rX /opt \
    && rm -rf /tmp/.cache /tmp/.local

USER 65532:65532

WORKDIR /sega-sms-python
