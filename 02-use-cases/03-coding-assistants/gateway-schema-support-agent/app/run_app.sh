#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"

mkdir -p exp/sessions

uv run streamlit run src/icarus/app.py \
    --server.port=8080 \
    --server.address=localhost \
    --browser.gatherUsageStats false
