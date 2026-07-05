FROM public.ecr.aws/ubuntu/ubuntu:26.04

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

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"
