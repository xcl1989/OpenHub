#!/bin/bash
pkill -9 -f "uvicorn app.main" 2>/dev/null
sleep 1
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
