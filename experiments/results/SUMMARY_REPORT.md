# Experiment Results — Personalised Learning System

Generated: 2026-05-03 17:09:32

## Experiment 1: Bloom Distribution vs Mastery

Tests whether question difficulty aligns with mastery level.

| Level | Alignment Score | Questions |
|-------|----------------|-----------|
| beginner | 0.8 | 5 |
| intermediate | 0.55 | 5 |
| advanced | 0.55 | 5 |

**Mean Alignment: 0.633**

## Experiment 2: Surprisal-Based UID Calibration

Surprisal model: gpt2 (124M, CPU)

| Concept | Level | Mean Surprisal (bits) | Surprisal StdDev | UID Score | FK Grade |
|---------|-------|-----------------------|-----------------|-----------|----------|
| Differential Manipulation | beginner | 5.0375 | 4.0633 | 0.1975 | 2.54 |
| Differential Manipulation | advanced | 4.7244 | 4.3279 | 0.1877 | 6.09 |

**Delta (Advanced - Beginner):**

| Metric | Delta | Expected Direction |
|--------|-------|--------------------|
| Mean Surprisal Change | -0.3131 | higher (more dense) |
| Uid Score Change | -0.0098 | slightly lower (tech bursts) |
| Fk Grade Change | +3.5500 | higher (harder reading) |

## Experiment 3: KG vs No-KG Quality Ablation

LLM-judged quality scores (1-5 scale).

| Metric | With KG | Without KG | Delta |
|--------|---------|------------|-------|
| Coherence | 5.0 | 5.0 | +0.00 |
| Prerequisite Awareness | 5.0 | 5.0 | +0.00 |
| Depth Calibration | 5.0 | 5.0 | +0.00 |
| Overall Quality | 5.0 | 5.0 | +0.00 |

## Experiment 4: Mastery Evolution Over Iterations

**Iterations per concept: 2**

| Metric | Value |
|--------|-------|
| With KG avg gain | 0.6969 |
| Without KG avg gain | 0.6969 |
| KG advantage | 0.0 |

**Vanishing and Exploding Gradients (with_kg):** 0.0 -> 0.2701 -> 0.6969
**Vanishing and Exploding Gradients (without_kg):** 0.0 -> 0.2701 -> 0.6969

## Experiment 5: Pedagogical Faithfulness Audit

| Metric | Score |
|--------|-------|
| Constructivist Adherence | 0% |
| Avg Scaffolding | 5.0/5 |
| Avg Clarity | 5.0/5 |
| Misconception Detection Rate | 100% |
| Avg Feedback Helpfulness | 5.0/5 |
