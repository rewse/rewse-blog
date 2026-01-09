FROM public.ecr.aws/ubuntu/ubuntu:24.04

# Amplify required packages: curl, git, openssh, bash
# Plus: libvips for image optimization, python3 for uv
# Plus: libffi-dev for cffi (required by pyvips)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    openssh-client \
    bash \
    ca-certificates \
    libvips-dev \
    libvips-tools \
    python3 \
    python3-dev \
    python3-pip \
    libffi-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"
