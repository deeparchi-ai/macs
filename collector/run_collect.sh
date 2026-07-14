#!/bin/bash
# MACS Balance Collector wrapper - exports API keys and runs collect_balance.py
# API keys should be set via environment or .env file, NOT hardcoded here.
# Copy .env.example to .env and fill in your keys.
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
export KIMI_API_KEY="${KIMI_API_KEY:-}"
cd /home/kuang/projects/macs && python3 collector/collect_balance.py
