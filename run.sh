#!/usr/bin/env bash
# Launch Toma Timer using the project venv.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Install deps if missing (fast no-op when already satisfied)
pip install -q -r requirements.txt 2>/dev/null || true

exec python src/main.py "$@"
