#!/usr/bin/env sh
set -e

PACKAGE="afx-hippocampus"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INTERACTIVE=false

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --interactive|-i) INTERACTIVE=true ;;
    esac
done

echo "==> Hippocampus Installer"
echo ""

# Find Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" > /dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required but not found."
    echo "Install Python from https://python.org and try again."
    exit 1
fi

# Check version
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt "$MIN_PYTHON_MAJOR" ] || { [ "$PY_MAJOR" -eq "$MIN_PYTHON_MAJOR" ] && [ "$PY_MINOR" -lt "$MIN_PYTHON_MINOR" ]; }; then
    echo "Error: Python >= ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR} required, found ${PY_VERSION}"
    exit 1
fi

echo "  Python: $PY_VERSION"

# Choose storage backend
STORAGE_TYPE="sqlite"
EXTRAS=""

if [ "$INTERACTIVE" = true ]; then
    echo ""
    echo "Choose storage backend:"
    echo "  1) SQLite (lightweight, zero-config, recommended for getting started)"
    echo "  2) PostgreSQL + pgvector (production-grade, requires a running PostgreSQL)"
    echo ""
    printf "  Enter choice [1]: "
    read -r CHOICE

    case "$CHOICE" in
        2)
            STORAGE_TYPE="postgresql"
            EXTRAS="[pg]"
            echo ""
            printf "  PostgreSQL URL (e.g. postgresql://user:pass@localhost/hippocampus): "
            read -r PG_URL
            ;;
        *)
            STORAGE_TYPE="sqlite"
            ;;
    esac
fi

# Install
echo ""
echo "  Installing ${PACKAGE}${EXTRAS}..."
$PYTHON -m pip install --quiet "${PACKAGE}${EXTRAS}"

# Init
HIPPOCAMPUS_HOME="${HIPPOCAMPUS_HOME:-$HOME/.hippocampus}"
mkdir -p "$HIPPOCAMPUS_HOME"

# Set storage type in config
if [ "$STORAGE_TYPE" = "postgresql" ] && [ -n "$PG_URL" ]; then
    export HIPPOCAMPUS_STORAGE_TYPE="postgresql"
    export HIPPOCAMPUS_PG_URL="$PG_URL"
fi

cd "$HIPPOCAMPUS_HOME"
hippocampus init --dir "$HIPPOCAMPUS_HOME" 2>/dev/null || true

# Update config with storage type if postgresql
if [ "$STORAGE_TYPE" = "postgresql" ]; then
    $PYTHON -c "
import json
p = '$HIPPOCAMPUS_HOME/hippocampus.json'
with open(p) as f:
    c = json.load(f)
c['storage_type'] = 'postgresql'
with open(p, 'w') as f:
    json.dump(c, f, indent=2)
" 2>/dev/null || true
fi

echo ""
echo "Hippocampus installed successfully!"
echo "  Storage: $STORAGE_TYPE"
echo ""
echo "Next steps:"
echo "  1. Set your LLM API key:"
echo "     export HIPPOCAMPUS_LLM_API_KEY=your-key-here"

if [ "$STORAGE_TYPE" = "postgresql" ] && [ -z "$PG_URL" ]; then
    echo ""
    echo "  2. Set your PostgreSQL URL:"
    echo "     export HIPPOCAMPUS_PG_URL=postgresql://user:pass@localhost/hippocampus"
    echo ""
    echo "  3. Start the server:"
    echo "     hippocampus start"
else
    echo ""
    echo "  2. Start the server:"
    echo "     hippocampus start"
fi

echo ""
echo "  API docs: http://localhost:8321/docs"
echo ""
