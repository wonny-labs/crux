FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang-18=1:18.1.3-1ubuntu1 \
        clangd-18=1:18.1.3-1ubuntu1 \
        clang-tidy-18=1:18.1.3-1ubuntu1 \
        libclang-rt-18-dev=1:18.1.3-1ubuntu1 \
        ccache \
        device-tree-compiler \
        file \
        gperf \
        git \
        libmagic1 \
        libsdl2-dev \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-tk \
        python3-venv \
        ripgrep \
        wget \
        xz-utils \
    && ln -sf /usr/bin/clangd-18 /usr/local/bin/clangd \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o vscode -g vscode /opt/crux-cache \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        west==1.4.0 \
        pytest==8.3.5

ENV CC=clang-18 \
    CXX=clang++-18

# Optional SEGGER J-Link software for the board Dev Container
# (.devcontainer/jlink/devcontainer.json sets CRUX_JLINK=1, see ADR-0007).
# The default container leaves CRUX_JLINK empty and installs nothing here. The
# package comes only from a file the developer downloaded and placed in
# .devcontainer/jlink/packages/; the build never downloads it.
ARG CRUX_JLINK=
ARG CRUX_JLINK_DEB=
ARG CRUX_JLINK_DEB_SHA256=
COPY .devcontainer/jlink/ /tmp/crux-jlink/
RUN if [ "$CRUX_JLINK" = 1 ]; then sh /tmp/crux-jlink/install-jlink.sh /tmp/crux-jlink/packages; fi \
    && rm -rf /tmp/crux-jlink
