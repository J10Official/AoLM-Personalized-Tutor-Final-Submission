"""
Experiment 2: Surprisal-Based Uniform Information Density (UID)

Measures whether explanations follow UID — the psycholinguistic principle
that good communicators distribute information uniformly across an utterance.

Uses GPT-2 small (124M params, CPU) to compute token-level surprisal:
    surprisal(t) = -log2 P(t | context)

Metrics:
- Mean Surprisal: avg information per token (bits). Higher = more complex.
- Surprisal Variance: how uniform is the information flow. Lower = more UID.
- UID Score: 1 / (1 + σ(surprisal)). Higher = better uniformity.
- Flesch-Kincaid Grade: classical readability metric for comparison.

Hypothesis: Beginner explanations should have lower mean surprisal and
higher UID score (smoother information flow). Advanced explanations should
have higher mean surprisal but still reasonable UID.
"""

import json
import os
import sys
import re
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.config import (
    configure_teacher_lm, load_knowledge_graph, create_fresh_learner,
    sample_concepts, RESULTS_DIR, setup_logging, timed
)

log = setup_logging("exp2")


# ===== Surprisal computation with GPT-2 =====

_gpt2_model = None
_gpt2_tokenizer = None


def _load_gpt2():
    """Lazy-load GPT-2 small. Cached after first call."""
    global _gpt2_model, _gpt2_tokenizer
    if _gpt2_model is not None:
        return _gpt2_model, _gpt2_tokenizer

    import torch
    from transformers import GPT2LMHeadModel, GPT2TokenizerFast

    log.info("Loading GPT-2 small for surprisal computation...")
    _gpt2_tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
    _gpt2_model = GPT2LMHeadModel.from_pretrained("gpt2")
    _gpt2_model.eval()
    log.info("GPT-2 loaded (124M params, CPU)")
    return _gpt2_model, _gpt2_tokenizer


def compute_surprisal(text: str, max_tokens: int = 512) -> dict:
    """
    Compute token-level surprisal using GPT-2.

    Returns:
        {
            "mean_surprisal": float,   # avg bits per token
            "surprisal_std": float,    # std dev of surprisal
            "uid_score": float,        # 1 / (1 + std). Higher = more uniform.
            "token_count": int,
            "surprisals": list[float], # per-token surprisal values
        }
    """
    import torch

    model, tokenizer = _load_gpt2()

    # Clean markdown/latex artifacts
    clean = re.sub(r"[#*_`$\\{}\[\]]", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()

    if not clean:
        return {"mean_surprisal": 0, "surprisal_std": 0, "uid_score": 1.0, "token_count": 0, "surprisals": []}

    # Tokenize (truncate to max_tokens for speed)
    inputs = tokenizer(clean, return_tensors="pt", truncation=True, max_length=max_tokens)
    input_ids = inputs["input_ids"]

    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        # Get per-token log probs
        logits = outputs.logits  # (1, seq_len, vocab_size)
        shift_logits = logits[:, :-1, :]
        shift_labels = input_ids[:, 1:]

        log_probs = torch.nn.functional.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs.gather(2, shift_labels.unsqueeze(-1)).squeeze(-1)

        # Surprisal = -log2(P(token|context))
        surprisals = (-token_log_probs / math.log(2)).squeeze(0).tolist()

    if not surprisals:
        return {"mean_surprisal": 0, "surprisal_std": 0, "uid_score": 1.0, "token_count": 0, "surprisals": []}

    mean_s = sum(surprisals) / len(surprisals)
    var_s = sum((s - mean_s) ** 2 for s in surprisals) / len(surprisals)
    std_s = math.sqrt(var_s)
    uid_score = 1.0 / (1.0 + std_s)

    return {
        "mean_surprisal": round(mean_s, 4),
        "surprisal_std": round(std_s, 4),
        "uid_score": round(uid_score, 4),
        "token_count": len(surprisals),
        "surprisals": [round(s, 2) for s in surprisals],  # keep for plotting
    }


def compute_fk_grade(text: str) -> float:
    """Compute Flesch-Kincaid grade level."""
    clean = re.sub(r"[#*_`$\\{}\[\]]", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()
    sentences = [s.strip() for s in re.split(r"[.!?]+", clean) if s.strip()]
    if not words or not sentences:
        return 0.0

    def syllables(word):
        word = word.lower()
        count = 0
        for i, ch in enumerate(word):
            if ch in "aeiou" and (i == 0 or word[i-1] not in "aeiou"):
                count += 1
        if word.endswith("e"):
            count -= 1
        return max(1, count)

    total_syl = sum(syllables(w) for w in words if w.isalpha())
    fk = 0.39 * (len(words) / len(sentences)) + 11.8 * (total_syl / len(words)) - 15.59
    return round(max(0, fk), 2)


# ===== Main experiment =====

def run_uid_experiment():
    log.info("=" * 60)
    log.info("EXPERIMENT 2: Surprisal-Based UID Calibration")
    log.info("=" * 60)

    # Pre-load GPT-2 before starting timer
    with timed(log, "Loading GPT-2"):
        _load_gpt2()

    with timed(log, "Configuring teacher LM"):
        lm = configure_teacher_lm()

    kg = load_knowledge_graph()

    from backend.agents.source_curator import SourceCuratorAgent
    from backend.agents.learning_curator import LearningCuratorAgent

    source_curator = SourceCuratorAgent(kg)
    learning_curator = LearningCuratorAgent(kg)

    concepts = sample_concepts(kg, n=1, strategy="diverse")
    log.info(f"Sampled {len(concepts)} concept(s) for UID analysis")

    results = []

    for cid, concept in concepts:
        concept_results = {"concept_id": cid, "concept_name": concept.name, "levels": {}}

        for level_name, mastery_val in [("beginner", 0.1), ("advanced", 0.8)]:
            learner = create_fresh_learner(f"uid_{level_name}")
            cs = learner.get_concept_state(cid)
            cs.mastery = mastery_val
            learner.enroll_in_course("experiment", [cid])

            with timed(log, f"[{level_name}] {concept.name}"):
                try:
                    source_result = source_curator.curate(learner, cid)
                    source_material = source_result.get("curated_document", concept.description)
                    session = learning_curator.create_session(learner, cid, source_material=source_material)
                    explanation = session.get("explanation", "")

                    # Compute surprisal-based UID
                    uid_metrics = compute_surprisal(explanation)
                    fk = compute_fk_grade(explanation)

                    concept_results["levels"][level_name] = {
                        "mean_surprisal": uid_metrics["mean_surprisal"],
                        "surprisal_std": uid_metrics["surprisal_std"],
                        "uid_score": uid_metrics["uid_score"],
                        "fk_grade": fk,
                        "token_count": uid_metrics["token_count"],
                        "word_count": len(explanation.split()),
                        "explanation_preview": explanation[:200] + "...",
                    }
                    log.info(f"  Surprisal={uid_metrics['mean_surprisal']:.2f}±{uid_metrics['surprisal_std']:.2f}, "
                             f"UID={uid_metrics['uid_score']:.3f}, FK={fk:.1f}")
                except Exception as e:
                    log.error(f"  Error: {e}")
                    concept_results["levels"][level_name] = {"error": str(e)}

        # Compute deltas
        beg = concept_results["levels"].get("beginner", {})
        adv = concept_results["levels"].get("advanced", {})
        if "error" not in beg and "error" not in adv:
            concept_results["uid_delta"] = {
                "mean_surprisal_change": round(adv["mean_surprisal"] - beg["mean_surprisal"], 4),
                "uid_score_change": round(adv["uid_score"] - beg["uid_score"], 4),
                "fk_grade_change": round(adv["fk_grade"] - beg["fk_grade"], 2),
            }

        results.append(concept_results)

    # Aggregate
    deltas = [r["uid_delta"] for r in results if "uid_delta" in r]
    avg_delta = {}
    if deltas:
        for key in deltas[0]:
            avg_delta[key] = round(sum(d[key] for d in deltas) / len(deltas), 4)

    report = {
        "experiment": "uid_surprisal_calibration",
        "model_used": "gpt2 (124M, CPU)",
        "per_concept_results": results,
        "average_delta": avg_delta,
        "interpretation": {
            "mean_surprisal_change": "> 0 means advanced explanations are more informationally dense",
            "uid_score_change": "< 0 is expected: advanced text is slightly less uniform (more technical bursts)",
            "fk_grade_change": "> 0 means advanced explanations have higher reading level",
        },
    }

    out_path = os.path.join(RESULTS_DIR, "exp2_uid_calibration.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    log.info("")
    log.info("=" * 40)
    log.info("UID Delta (Advanced - Beginner):")
    for k, v in avg_delta.items():
        direction = "↑" if v > 0 else "↓" if v < 0 else "="
        log.info(f"  {k:30s}: {v:+.4f} {direction}")
    log.info(f"Results → {out_path}")

    return report


if __name__ == "__main__":
    run_uid_experiment()
