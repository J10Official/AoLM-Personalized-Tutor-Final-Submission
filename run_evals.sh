#!/usr/bin/env bash
# ============================================================
# run_evals.sh — Run synthetic evaluations and ablation studies
# Runs the automated experiment framework in experiments/
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  DeepLearn — Synthetic Evaluation & Ablation${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Use venv Python if available
PYTHON="python3"
if [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
    echo -e "${GREEN}Using virtualenv Python${NC}"
fi

# Load .env for API keys
if [ -f "$PROJECT_DIR/backend/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/backend/.env" | xargs)
    echo -e "${GREEN}Loaded API keys from backend/.env${NC}"
fi

# Check required env
if [ -z "$GOOGLE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}ERROR: No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in backend/.env${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# Parse arguments
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ./run_evals.sh all           Run all 5 experiments"
    echo -e "  ./run_evals.sh 1             Run experiment 1 (Bloom Distribution)"
    echo -e "  ./run_evals.sh 2             Run experiment 2 (UID Calibration)"
    echo -e "  ./run_evals.sh 3             Run experiment 3 (KG vs No-KG)"
    echo -e "  ./run_evals.sh 4             Run experiment 4 (Mastery Evolution)"
    echo -e "  ./run_evals.sh 5             Run experiment 5 (Faithfulness)"
    echo -e "  ./run_evals.sh summary       Regenerate summary report"
    echo -e "  ./run_evals.sh synthetic     Run legacy synthetic eval"
    echo ""
    echo -e "  Results are saved to experiments/results/"
    exit 0
fi

case "$1" in
    all)
        echo -e "${GREEN}Running all experiments...${NC}"
        $PYTHON experiments/run_all.py
        ;;
    summary)
        echo -e "${GREEN}Regenerating summary report...${NC}"
        $PYTHON experiments/run_all.py --summary
        ;;
    synthetic)
        echo -e "${GREEN}Running legacy synthetic evaluation...${NC}"
        $PYTHON run_synthetic_eval.py
        ;;
    [1-5])
        echo -e "${GREEN}Running experiment $1...${NC}"
        $PYTHON experiments/run_all.py --exp "$1"
        ;;
    *)
        echo -e "${RED}Unknown argument: $1${NC}"
        echo "Run ./run_evals.sh without arguments for usage."
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done. Results in experiments/results/${NC}"
