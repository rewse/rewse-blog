#!/bin/bash
# Wrapper script for optimize_images.py using pyvips

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

exec uv run --with pyvips scripts/optimize_images.py "$@"
