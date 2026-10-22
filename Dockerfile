FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM public.ecr.aws/ubuntu/ubuntu:26.04@sha256:51e35c02a42cf2a6646c5879f5752b38098ed0a20056a989f0af3a3c5e697c9a

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
