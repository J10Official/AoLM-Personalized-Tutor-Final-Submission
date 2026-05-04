#!/usr/bin/env bash
# ============================================================
# run_admin.sh — Start the Human-in-the-Loop Flywheel Admin
# Launches backend API + Vite frontend (with /api proxy).
# Access the admin panel at http://localhost:5174/admin.html
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
ADMIN_PORT=5174

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  DeepLearn — Flywheel Admin Dashboard${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Kill stale processes
kill -9 $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
kill -9 $(lsof -t -i:$ADMIN_PORT) 2>/dev/null || true
sleep 1

# Trap Ctrl+C
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $ADMIN_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $ADMIN_PID 2>/dev/null || true
    echo -e "${GREEN}Admin dashboard stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Use venv Python if available
PYTHON="python3"
if [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
    echo -e "${GREEN}Using virtualenv Python${NC}"
fi

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Start Backend
echo -e "${GREEN}Starting backend on port $BACKEND_PORT...${NC}"
cd "$PROJECT_DIR"
$PYTHON -m uvicorn backend.api.server:app --host 0.0.0.0 --port $BACKEND_PORT 2>&1 &
BACKEND_PID=$!

# Start frontend via Vite (handles /api proxy to backend)
echo -e "${GREEN}Starting admin interface on port $ADMIN_PORT...${NC}"
cd "$PROJECT_DIR/frontend"
npx vite --port $ADMIN_PORT 2>&1 &
ADMIN_PID=$!

sleep 2

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Backend API:${NC}     http://localhost:$BACKEND_PORT"
echo -e "  ${GREEN}Admin Panel:${NC}     http://localhost:$ADMIN_PORT/admin.html"
echo -e ""
echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

wait $BACKEND_PID $ADMIN_PID
