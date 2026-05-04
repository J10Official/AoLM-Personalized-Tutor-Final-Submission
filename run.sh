#!/usr/bin/env bash
# ============================================================
# run.sh — Start the Personalised Learning System
# Launches backend (FastAPI/Uvicorn) and frontend (Vite) simultaneously.
# Press Ctrl+C to stop both.
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Create logs directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Timestamped log files
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKEND_LOG="$LOG_DIR/backend_${TIMESTAMP}.log"
FRONTEND_LOG="$LOG_DIR/frontend_${TIMESTAMP}.log"

# Also maintain a "latest" symlink for quick access
BACKEND_LATEST="$LOG_DIR/backend_latest.log"
FRONTEND_LATEST="$LOG_DIR/frontend_latest.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  DeepLearn — Personalised Learning System${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Kill any existing processes on our ports
echo -e "${YELLOW}Cleaning up stale processes...${NC}"
kill -9 $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
kill -9 $(lsof -t -i:$FRONTEND_PORT) 2>/dev/null || true
sleep 1

# Trap Ctrl+C to kill both child processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}All services stopped.${NC}"
    echo -e "  Backend log:  ${BACKEND_LOG}"
    echo -e "  Frontend log: ${FRONTEND_LOG}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Check Python venv
PYTHON="python3"
if [ -d "$PROJECT_DIR/.venv" ]; then
    echo -e "${GREEN}Using Python virtualenv...${NC}"
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi

# Set PYTHONPATH so uvicorn can find backend modules
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Start Backend (with tee to log + console)
echo -e "${GREEN}Starting backend on port $BACKEND_PORT...${NC}"
echo -e "  Logging to: ${BACKEND_LOG}"
cd "$PROJECT_DIR"
$PYTHON -m uvicorn backend.api.server:app --host 0.0.0.0 --port $BACKEND_PORT --reload 2>&1 | tee -a "$BACKEND_LOG" &
BACKEND_PID=$!
echo -e "  Backend PID: $BACKEND_PID"

# Create latest symlinks
ln -sf "$BACKEND_LOG" "$BACKEND_LATEST"

# Start Frontend (with tee to log + console)
echo -e "${GREEN}Starting frontend on port $FRONTEND_PORT...${NC}"
echo -e "  Logging to: ${FRONTEND_LOG}"
cd "$PROJECT_DIR/frontend"
npx vite --port $FRONTEND_PORT 2>&1 | tee -a "$FRONTEND_LOG" &
FRONTEND_PID=$!
echo -e "  Frontend PID: $FRONTEND_PID"

ln -sf "$FRONTEND_LOG" "$FRONTEND_LATEST"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Backend:${NC}  http://localhost:$BACKEND_PORT"
echo -e "  ${GREEN}Frontend:${NC} http://localhost:$FRONTEND_PORT"
echo -e "  ${GREEN}Admin:${NC}    http://localhost:$FRONTEND_PORT/admin.html"
echo -e ""
echo -e "  ${YELLOW}Logs:${NC}     $LOG_DIR/"
echo -e "  ${YELLOW}Press Ctrl+C to stop both services${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
