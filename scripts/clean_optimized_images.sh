#!/bin/bash
# Clean all optimized images including manifest to force regeneration

OPTIMIZED_DIR="${OPTIMIZED_IMAGES_DIR:-static/img/optimized}"

if [ -d "$OPTIMIZED_DIR" ]; then
    echo "Cleaning optimized images directory: $OPTIMIZED_DIR"
    rm -rf "$OPTIMIZED_DIR"/*
    rm -f "$OPTIMIZED_DIR/.manifest.json"
    echo "Cleaned successfully"
else
    echo "Directory not found: $OPTIMIZED_DIR"
    exit 1
fi
