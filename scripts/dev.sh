#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel

# Install in editable mode with dev extras (from pyproject.toml)
python -m pip install -e ".[dev]"

echo
echo "OK: venv ready"
echo "Try: aris ping"
