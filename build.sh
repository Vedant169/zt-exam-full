#!/usr/bin/env bash
# Render build script
set -o errexit

echo "=== Installing dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Seeding database ==="
cd backend
python seed.py
cd ..

echo "=== Build complete ==="
