FROM ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f AS uv

FROM public.ecr.aws/ubuntu/ubuntu:26.04@sha256:51c73e2050b35e6f280a3dc97094b0f511ff56ae62f1cf008e3796626555ac89

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
