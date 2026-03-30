#!/bin/bash
# JRM Showcase — Build Script
# Runs scraper then generator to produce the static site.

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "========================================"
echo "  JRM Showcase Build"
echo "========================================"
echo ""

# Step 1: Scrape
echo "[1/3] Running scraper..."
python3 scraper.py

# Step 2: Generate HTML
echo ""
echo "[2/3] Generating HTML site..."
python3 generator.py

# Step 3: Generate PDFs
echo ""
echo "[3/3] Generating PDFs..."
python3 pdf_generator.py

echo ""
echo "Build complete. Output in ./output/"
echo ""
