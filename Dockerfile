FROM public.ecr.aws/ubuntu/ubuntu:24.04

# Amplify required packages: curl, git, openssh, bash
# Plus: libvips for image optimization, python3 for uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    openssh-client \
    bash \
    ca-certificates \
    libvips-dev \
    libvips-tools \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"
