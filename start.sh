#!/bin/bash
# Start script for Railway deployment
# Handles PORT environment variable properly

PORT="${PORT:-8080}"
echo "Starting Knowledge Extractor API on port $PORT"
exec gunicorn app:app --bind "0.0.0.0:$PORT" --workers 2 --timeout 120
