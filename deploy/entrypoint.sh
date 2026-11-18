#!/bin/sh
set -e
echo "Running seed (skips if data exists)..."
python3 seed.py
echo "Starting API server..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
