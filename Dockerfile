FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

FROM public.ecr.aws/ubuntu/ubuntu:26.04@sha256:938ad41df0a284241e950ddbf669ae8f8aaf86ba105e04bdbb81c66fbc5cbc3f

# Amplify required packages: curl, git, openssh, bash
# Plus: libvips for image optimization, python3 for uv
# Plus: libffi-dev for cffi (required by pyvips)
# Plus: libheif-dev and rav1e for AVIF support (AV1 compression)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    gcc \
    git \
    libffi-dev \
    libheif-dev \
    libheif-plugin-aomdec \
    libheif-plugin-aomenc \
    libheif-plugin-rav1e \
    librav1e0.8 \
    libvips-dev \
    libvips-tools \
    openssh-client \
    pkg-config \
    python3 \
    python3-dev \
    rav1e \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from its image, pinned by digest, instead of piping an installer into sh.
COPY --from=uv /uv /uvx /usr/local/bin/
