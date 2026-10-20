"""Regenerate reports/fingerprint/rule_weights_sensitivity.v1.json: rule-drift scores under alternative field weights.

Uses the changed fields stored for each held-out transition in heldout_transitions.v2.json (rule-drift-v1.2), so no pipeline
run and no model is needed. The active weights are not changed. Run from the repository root:
    python reports/fingerprint/rule_weights_sensitivity.v1.py
"""

import json
import statistics
from itertools import combinations
from pathlib import Path

CURRENT = {name: row["weight"] for name, row in json.loads(Path("configs/metrics/rule_drift.v1.2.json").read_text())["fields"].items()}
# Reasonable alternatives, each summing to 100: no tiers; flatter tiers; no discount for the heuristic fields; a heavier core.
ALTERNATIVES = {
    "current": CURRENT,
    "equal": dict.fromkeys(CURRENT, 12.5),
    "flatter_tiers": {"modality": 20, "penalty": 15, "threshold": 15, "deadline": 15, "exception": 12.5, "scope": 12.5, "actor": 5, "action": 5},
    "no_heuristic_discount": {"modality": 20, "penalty": 40 / 3, "threshold": 40 / 3, "deadline": 40 / 3, "exception": 10, "scope": 10, "actor": 10, "action": 10},
    "core_heavy": {"modality": 35, "penalty": 15, "threshold": 15, "deadline": 15, "exception": 7.5, "scope": 7.5, "actor": 2.5, "action": 2.5},
}


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    out, i = [0.0] * len(values), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / ((sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5)


rows = [row for row in json.loads(Path("reports/fingerprint/heldout_transitions.v2.json").read_text())["rows"] if row["rule"][1] is not None]
fields = [row["rule"][2] for row in rows]
for weights in ALTERNATIVES.values():
    assert abs(sum(weights.values()) - 100) < 1e-9
violations = [row["transition_id"] for row, changed in zip(rows, fields) if sum(CURRENT[f] for f in changed) != row["rule"][1]]
current = [sum(CURRENT[f] for f in changed) for changed in fields]
summary = {}
for name, weights in ALTERNATIVES.items():
    scores = [sum(weights[f] for f in changed) for changed in fields]
    strict = [(i, j) for i, j in combinations(range(len(rows)), 2) if current[i] != current[j] and scores[i] != scores[j]]
    kept = sum((current[i] < current[j]) == (scores[i] < scores[j]) for i, j in strict)
    ties_changed = sum((current[i] == current[j]) != (scores[i] == scores[j]) for i, j in combinations(range(len(rows)), 2))
    changes = [abs(a - b) for a, b in zip(scores, current)]
    summary[name] = {"weights": weights, "median": statistics.median(scores), "max": max(scores),
                     "spearman_vs_current": round(spearman(scores, current), 3),
                     "ordered_pairs_kept_percent": round(100 * kept / len(strict), 1) if strict else None,
                     "pairs_whose_tie_status_changed": ties_changed,
                     "median_abs_change": round(statistics.median(changes), 2), "max_abs_change": round(max(changes), 2)}
counts = {}
for changed in fields:
    for field in changed:
        counts[field] = counts.get(field, 0) + 1
out = {"schema_version": "1.0.0", "method": "rule-drift-v1.2 field weights; alternatives applied to the stored changed fields",
       "transitions_scored": len(rows), "changed_field_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
       "weightings": summary, "invariant_violations": violations,
       "finding": (
           f"Tiered alternatives keep the order of rule scores (Spearman {min(summary[n]['spearman_vs_current'] for n in ('flatter_tiers', 'no_heuristic_discount', 'core_heavy')):.3f} or more "
           f"against the current weights; at least {min(summary[n]['ordered_pairs_kept_percent'] for n in ALTERNATIVES):.1f}% of strictly ordered pairs keep their order under every alternative). "
           f"Removing the tiers (equal weights) mostly changes ties: {summary['equal']['pairs_whose_tie_status_changed']} pairs switch between tied and ordered "
           f"(Spearman {summary['equal']['spearman_vs_current']:.3f}). So the tier structure, more than the exact numbers, decides which changes score alike. "
           f"The most often changed field is {max(counts, key=counts.get)} ({counts[max(counts, key=counts.get)]} of {len(rows)} changes); "
           "actor and action are the heuristic fields, so their low weight limits how much extraction errors move the scores."),
       "note": "No expert labels exist, so no weighting is shown to be more correct; this checks stability only. Legal validation: UNVERIFIED."}
Path("reports/fingerprint/rule_weights_sensitivity.v1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items()}, ensure_ascii=False, indent=1))
