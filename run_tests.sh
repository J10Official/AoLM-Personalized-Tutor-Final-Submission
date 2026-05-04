#!/usr/bin/env bash
# ============================================================
# run_tests.sh — Run unit and integration tests
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  DeepLearn — Test Suite${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Use venv Python if available
PYTHON="python3"
if [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
    echo -e "${GREEN}Using virtualenv Python${NC}"
fi

# Check pytest is installed
if ! $PYTHON -m pytest --version &>/dev/null; then
    echo -e "${YELLOW}Installing pytest...${NC}"
    $PYTHON -m pip install pytest -q
fi

# Parse arguments
ARGS="${@:---tb=short -v}"

echo -e "${GREEN}Running tests in testing/ ...${NC}"
echo ""

cd "$PROJECT_DIR"
$PYTHON -m pytest testing/ $ARGS

echo ""
echo -e "${GREEN}All tests complete.${NC}"
