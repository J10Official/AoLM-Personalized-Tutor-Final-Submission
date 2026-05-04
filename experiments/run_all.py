#!/usr/bin/env python3
"""
Run All Experiments — Master Runner

Usage:
    python experiments/run_all.py            # Run all
    python experiments/run_all.py --exp 1    # Run specific
    python experiments/run_all.py --summary  # Generate report from existing results
"""

import argparse
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from experiments.config import RESULTS_DIR


def run_experiment(exp_num: int):
    """Run a single experiment by number."""
    start = time.time()

    if exp_num == 1:
        from experiments.exp1_bloom_distribution import run_bloom_experiment
        report = run_bloom_experiment()
    elif exp_num == 2:
        from experiments.exp2_uid_calibration import run_uid_experiment
        report = run_uid_experiment()
    elif exp_num == 3:
        from experiments.exp3_kg_ablation import run_kg_ablation
        report = run_kg_ablation()
    elif exp_num == 4:
        from experiments.exp4_mastery_evolution import run_mastery_evolution
        report = run_mastery_evolution()
    elif exp_num == 5:
        from experiments.exp5_pedagogical_faithfulness import run_pedagogical_faithfulness
        report = run_pedagogical_faithfulness()
    else:
        print(f"Unknown experiment number: {exp_num}")
        return None

    elapsed = time.time() - start
    report["runtime_seconds"] = round(elapsed, 1)
    print(f"\n⏱ Experiment {exp_num} completed in {elapsed:.1f}s")
    return report


def generate_summary_report():
    """Combine all result JSONs into a single summary markdown report."""
    results = {}
    for fname in sorted(os.listdir(RESULTS_DIR)):
        if fname.endswith(".json") and fname.startswith("exp"):
            with open(os.path.join(RESULTS_DIR, fname)) as f:
                results[fname] = json.load(f)

    if not results:
        print("No results found. Run experiments first.")
        return

    lines = [
        "# Experiment Results — Personalised Learning System",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # Exp 1: Bloom
    if "exp1_bloom_distribution.json" in results:
        r = results["exp1_bloom_distribution.json"]
        lines.extend([
            "## Experiment 1: Bloom Distribution vs Mastery",
            "",
            "Tests whether question difficulty aligns with mastery level.",
            "",
            "| Level | Alignment Score | Questions |",
            "|-------|----------------|-----------|",
        ])
        for level in ["beginner", "intermediate", "advanced"]:
            score = r.get("alignment_scores", {}).get(level, "N/A")
            count = r.get("raw_counts", {}).get(level, 0)
            lines.append(f"| {level} | {score} | {count} |")
        lines.extend(["", f"**Mean Alignment: {r.get('mean_alignment', 'N/A')}**", ""])

    # Exp 2: UID Surprisal
    if "exp2_uid_calibration.json" in results:
        r = results["exp2_uid_calibration.json"]
        delta = r.get("average_delta", {})
        lines.extend([
            "## Experiment 2: Surprisal-Based UID Calibration",
            "",
            f"Surprisal model: {r.get('model_used', 'gpt2')}",
            "",
        ])
        # Raw values
        concepts = r.get("per_concept_results", [])
        if concepts:
            lines.extend([
                "| Concept | Level | Mean Surprisal (bits) | Surprisal StdDev | UID Score | FK Grade |",
                "|---------|-------|-----------------------|-----------------|-----------|----------|",
            ])
            for cr in concepts:
                for lvl in ["beginner", "advanced"]:
                    lv = cr.get("levels", {}).get(lvl, {})
                    if "error" not in lv:
                        lines.append(
                            f"| {cr['concept_name'][:25]} | {lvl} "
                            f"| {lv.get('mean_surprisal', 'N/A')} "
                            f"| {lv.get('surprisal_std', 'N/A')} "
                            f"| {lv.get('uid_score', 'N/A')} "
                            f"| {lv.get('fk_grade', 'N/A')} |"
                        )
            lines.append("")
        # Delta
        if delta:
            lines.extend(["**Delta (Advanced - Beginner):**", ""])
            lines.extend(["| Metric | Delta | Expected Direction |", "|--------|-------|--------------------|"])
            expected_dir = {
                "mean_surprisal_change": "higher (more dense)",
                "uid_score_change": "slightly lower (tech bursts)",
                "fk_grade_change": "higher (harder reading)",
            }
            for k, v in delta.items():
                arrow = "+" if v > 0 else "" if v < 0 else ""
                lines.append(f"| {k.replace('_', ' ').title()} | {arrow}{v:.4f} | {expected_dir.get(k, '')} |")
            lines.append("")

    # Exp 3: KG Ablation
    if "exp3_kg_ablation.json" in results:
        r = results["exp3_kg_ablation.json"]
        s = r.get("summary", {})
        wk = s.get("with_kg_averages", {})
        nk = s.get("without_kg_averages", {})
        d = s.get("delta", {})
        lines.extend([
            "## Experiment 3: KG vs No-KG Quality Ablation",
            "",
            "LLM-judged quality scores (1-5 scale).",
            "",
            "| Metric | With KG | Without KG | Delta |",
            "|--------|---------|------------|-------|",
        ])
        for metric in wk:
            lines.append(f"| {metric.replace('_', ' ').title()} | {wk[metric]} | {nk.get(metric, 'N/A')} | {d.get(metric, 0):+.2f} |")
        lines.append("")

    # Exp 4: Mastery Evolution
    if "exp4_mastery_evolution.json" in results:
        r = results["exp4_mastery_evolution.json"]
        s = r.get("summary", {})
        lines.extend([
            "## Experiment 4: Mastery Evolution Over Iterations",
            "",
            f"**Iterations per concept: {r.get('iterations', 'N/A')}**",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| With KG avg gain | {s.get('with_kg_avg_gain', 'N/A')} |",
            f"| Without KG avg gain | {s.get('without_kg_avg_gain', 'N/A')} |",
            f"| KG advantage | {s.get('kg_advantage', 'N/A')} |",
            "",
        ])
        for result in r.get("per_concept_results", []):
            traj = " -> ".join(str(m) for m in result.get("mastery_trajectory", []))
            lines.append(f"**{result['concept_name']} ({result['mode']}):** {traj}")
        lines.append("")

    # Exp 5: Pedagogical Faithfulness
    if "exp5_pedagogical_faithfulness.json" in results:
        r = results["exp5_pedagogical_faithfulness.json"]
        s = r.get("summary", {})
        c = s.get("constructivist", {})
        m = s.get("misconception", {})

        adherence = c.get("adherence_rate", "N/A")
        detection = m.get("detection_rate", "N/A")
        adh_str = f"{adherence:.0%}" if isinstance(adherence, float) else str(adherence)
        det_str = f"{detection:.0%}" if isinstance(detection, float) else str(detection)

        lines.extend([
            "## Experiment 5: Pedagogical Faithfulness Audit",
            "",
            "| Metric | Score |",
            "|--------|-------|",
            f"| Constructivist Adherence | {adh_str} |",
            f"| Avg Scaffolding | {c.get('avg_scaffolding', 'N/A')}/5 |",
            f"| Avg Clarity | {c.get('avg_clarity', 'N/A')}/5 |",
            f"| Misconception Detection Rate | {det_str} |",
            f"| Avg Feedback Helpfulness | {m.get('avg_feedback_helpfulness', 'N/A')}/5 |",
            "",
        ])

    report_text = "\n".join(lines)
    report_path = os.path.join(RESULTS_DIR, "SUMMARY_REPORT.md")
    with open(report_path, "w") as f:
        f.write(report_text)

    print(f"\n📄 Summary report saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Run Personalised Learning System experiments")
    parser.add_argument("--exp", type=int, default=0, help="Experiment number (1-5). 0 = run all.")
    parser.add_argument("--summary", action="store_true", help="Generate summary report from existing results")
    args = parser.parse_args()

    if args.summary:
        generate_summary_report()
        return

    if args.exp == 0:
        total_start = time.time()
        for i in range(1, 6):
            print(f"\n{'#' * 60}")
            print(f"#  RUNNING EXPERIMENT {i}/5")
            print(f"{'#' * 60}")
            try:
                run_experiment(i)
            except Exception as e:
                print(f"\n✗ Experiment {i} failed: {e}")
                import traceback
                traceback.print_exc()
        print(f"\n{'='*60}")
        print(f"All experiments completed in {time.time() - total_start:.1f}s")
        generate_summary_report()
    else:
        run_experiment(args.exp)
        generate_summary_report()


if __name__ == "__main__":
    main()
