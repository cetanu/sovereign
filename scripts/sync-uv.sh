#!/usr/bin/env bash
cd /proj
export PATH="$HOME/.local/bin:$PATH"
pip install uv
uv sync --all-extras
uv lock
