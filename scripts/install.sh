#!/usr/bin/env sh
set -e

PACKAGE="hebb-mind"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INTERACTIVE=false
LANGUAGE="auto"
REGION="auto"
PROFILE="default"

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --interactive|-i) INTERACTIVE=true ;;
        --language=*) LANGUAGE="${arg#*=}" ;;
        --region=*) REGION="${arg#*=}" ;;
        --profile=*) PROFILE="${arg#*=}" ;;
    esac
done

echo "==> Hebb Mind Installer"
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
            printf "  PostgreSQL URL (e.g. postgresql://user:pass@localhost/hebb): "
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

# Setup
HEBB_HOME="${HEBB_HOME:-$HOME/.hebb}"
mkdir -p "$HEBB_HOME"

cd "$HEBB_HOME"
hebb setup --language "$LANGUAGE" --region "$REGION" --profile "$PROFILE"

# Update config with storage type if postgresql
if [ "$STORAGE_TYPE" = "postgresql" ]; then
    hebb config set storage_type postgresql
    if [ -n "$PG_URL" ]; then
        hebb config set pg_url "$PG_URL"
    fi
fi

echo ""
echo "Hebb Mind installed successfully!"
echo "  Storage: $STORAGE_TYPE"
echo ""
echo "Next steps:"
echo "  1. Optional: enable memory consolidation with an LLM:"
echo "     hebb config set llm_api_key your-key-here"

if [ "$STORAGE_TYPE" = "postgresql" ] && [ -z "$PG_URL" ]; then
    echo ""
    echo "  2. Set your PostgreSQL URL:"
    echo "     hebb config set pg_url postgresql://user:pass@localhost/hebb"
    echo ""
    echo "  3. Install the background service (launchd / systemd / Task Scheduler):"
    echo "     hebb service install"
else
    echo ""
    echo "  2. Install the background service (launchd / systemd / Task Scheduler):"
    echo "     hebb service install"
fi

echo ""
echo "  API docs: http://localhost:8321/docs"
echo ""
