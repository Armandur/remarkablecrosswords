#!/usr/bin/env bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload 2>&1 | tee dev.log
