#!/bin/bash
# Wrapper script for optimize_images.py that reads API key from 1Password

set -e

export SHORTPIXEL_API_KEY=$(op read "op://rewse-blog/ShortPixel/credential")

exec uv run --with requests scripts/optimize_images.py "$@"
