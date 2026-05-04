# Experiments — Personalised Learning System

Automated experiments for evaluating the system's pedagogical effectiveness.
All experiments use **gemma-3-27b** as a simulated student and **gemma-4-31b** as the system teacher.

## Quick Start

```bash
cd PersonalisedLearningSystem

# Activate virtual environment
source .venv/bin/activate
export PYTHONPATH=.

# Run ALL experiments (takes ~5-10 min)
python experiments/run_all.py

# Run a specific experiment
python experiments/run_all.py --exp 1   # Bloom distribution
python experiments/run_all.py --exp 2   # UID calibration
python experiments/run_all.py --exp 3   # KG ablation
python experiments/run_all.py --exp 4   # Mastery evolution
python experiments/run_all.py --exp 5   # Pedagogical faithfulness

# Generate summary from existing results
python experiments/run_all.py --summary
```

## Experiments

### Experiment 1: Bloom Distribution vs Mastery
**File:** `exp1_bloom_distribution.py`  
**Question:** Does the system generate questions at the right Bloom's taxonomy level for the learner's mastery?

- Tests 3 mastery levels (beginner, intermediate, advanced) × 2 concepts each
- Measures alignment between expected and actual Bloom distributions
- **Metric:** Alignment score (0-1, 1 = perfect match to expected distribution)

### Experiment 2: UID — Explanation Complexity Calibration
**File:** `exp2_uid_calibration.py`  
**Question:** Do explanations adapt their complexity based on mastery level?

- Generates explanations for the SAME concept at beginner and advanced levels
- Compares linguistic metrics
- **Metrics:**
  - Type-Token Ratio (TTR): vocabulary diversity
  - Flesch-Kincaid Grade Level: reading difficulty
  - Technical Term Density: fraction of long/technical words
  - Average Word Length: simple proxy for complexity

### Experiment 3: KG vs No-KG Quality Ablation
**File:** `exp3_kg_ablation.py`  
**Question:** Does the knowledge graph improve output quality?

- Generates explanations with and without KG (prerequisite awareness, related concepts)
- LLM-as-judge scores on 4 dimensions (1-5 scale)
- **Metrics:** Coherence, Prerequisite Awareness, Depth Calibration, Overall Quality

### Experiment 4: Mastery Evolution Over Learning Iterations
**File:** `exp4_mastery_evolution.py`  
**Question:** Does KG-based personalisation lead to faster mastery growth?

- Simulates a student (gemma-3-27b) going through 3 learning cycles per concept
- Each cycle: explanation → questions → student answers → evaluation → mastery update
- Compares mastery trajectory with and without KG
- **Metrics:** Mastery gain, score trajectory, KG advantage

### Experiment 5: Pedagogical Faithfulness Audit (LLM-Based Eval)
**File:** `exp5_pedagogical_faithfulness.py`  
**Question:** Does the system follow its own pedagogical principles?

- **Test A — Constructivist Constraint:** Do doubt resolutions only use known concepts?
- **Test B — Misconception Detection:** Does the system catch deliberately wrong answers?
- LLM-as-judge evaluates adherence
- **Metrics:** Constructivist adherence rate, scaffolding score, misconception detection rate

## Results

Results are saved to `experiments/results/`:
- `exp1_bloom_distribution.json`
- `exp2_uid_calibration.json`
- `exp3_kg_ablation.json`
- `exp4_mastery_evolution.json`
- `exp5_pedagogical_faithfulness.json`
- `SUMMARY_REPORT.md` — combined human-readable report

## Configuration

Edit `experiments/config.py` to adjust:
- `NUM_CONCEPTS_PER_EXPERIMENT` — concepts per run (default: 4)
- `NUM_LEARNING_ITERATIONS` — learning cycles in Exp 4 (default: 3)
- `STUDENT_MODEL` — the simulated student LLM
- `TEACHER_MODEL` — the system's agent LLM

## Cost Estimate

With default settings (~2-3 concepts per experiment, 3 iterations):
- **Experiment 1:** ~6 LLM calls (question generation)
- **Experiment 2:** ~6 LLM calls (source curation + explanation)
- **Experiment 3:** ~12 LLM calls (2 modes × 3 concepts × 2 calls + judge)
- **Experiment 4:** ~24 LLM calls (2 modes × 2 concepts × 3 iterations × 2 calls)
- **Experiment 5:** ~10 LLM calls (doubt resolution + evaluation + judges)
- **Total:** ~58 LLM calls, estimated 3-8 minutes
