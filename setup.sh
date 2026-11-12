#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--optional" ) ]]; then
    echo "Usage: bash setup.sh [--optional]" >&2
    exit 2
fi

INDEX_URL="${PIP_INDEX_URL:-https://pypi-mirror.gitverse.ru/simple/}"
VERSION_CHECK='import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10 or newer is required.")'
VENV_PYTHON=".venv/bin/python"

if [[ ! -e .venv ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Install Python 3.10 or newer, then rerun this script." >&2
        exit 1
    fi
    python3 -c "$VERSION_CHECK"
    python3 -m venv .venv
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "The existing .venv is not a working macOS environment. Move it aside and rerun this script." >&2
    exit 1
fi

"$VENV_PYTHON" -c "$VERSION_CHECK"
"$VENV_PYTHON" -m pip config --site set global.index-url "$INDEX_URL"
"$VENV_PYTHON" -m pip install --index-url "$INDEX_URL" -r requirements.txt

if [[ "${1:-}" == "--optional" ]]; then
    "$VENV_PYTHON" -m pip install --index-url "$INDEX_URL" -r requirements-optional.txt
fi

echo "Setup complete. Select .venv/bin/python as the notebook kernel in VS Code."
