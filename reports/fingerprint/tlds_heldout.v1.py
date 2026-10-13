"""Regenerate reports/fingerprint/tlds_heldout.v1.json: tlds-v1 over the 86 held-out transitions, with alternative weights.

Offline (no model, no live source). Run from the repository root:
    TLD_LIVE_INDIA_CODE=0 TLD_RAG_PROVIDER=openai_compatible TLD_RAG_API_KEY= OPENAI_API_KEY= TLD_RULE_DELTA_LLM=0 \
    PYTHONPATH=src python reports/fingerprint/tlds_heldout.v1.py
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from temporal_legal_drift.rag import fingerprint as fp
from temporal_legal_drift.rag.audit import offline_extractive
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

WEIGHTINGS = {"default": None, "equal": dict.fromkeys(fp.TLDS_COMPONENTS, 0.25),
              "legal_heavy": {"textual": 0.1, "semantic": 0.1, "legal_effect": 0.6, "rule_structure": 0.2},
              "wording_heavy": {"textual": 0.4, "semantic": 0.4, "legal_effect": 0.1, "rule_structure": 0.1}}


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
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


v2 = json.loads(Path("reports/fingerprint/heldout_transitions.v2.json").read_text())
pipe, rows, violations = RagPipeline(Path(".")), [], []
with offline_extractive():
    for old in v2["rows"]:
        f = pipe.answer(old["query"], "specific")["fingerprint"]
        t, parts = f["tlds"], {n: c["value"] for n, c in f["tlds"]["components"].items()}
        if [f["wording_drift"]["value"], f["rule_drift"]["value"]] != [old["wording"][1], old["rule"][1]]:
            violations.append(f"{old['transition_id']}: v1.2 wording or rule value changed")
        if t["value"] is not None and not (0 <= t["value"] <= 100 and abs(t["value"] - 100 * sum(t["weights"][n] * parts[n] for n in parts)) < 1e-9):
            violations.append(f"{old['transition_id']}: composite out of bounds or not the weighted sum")
        if t["value"] is None and old["wording"][0] == "DETERMINED" and old["rule"][1] is not None:
            violations.append(f"{old['transition_id']}: incomplete although wording and rule were scored")
        rows.append({"transition_id": old["transition_id"], "query": old["query"], "state": t["state"], "missing": t["missing_components"],
                     "components": parts, "by_weighting": {name: fp.composite(parts, w)["value"] for name, w in WEIGHTINGS.items()},
                     "partial_value": t["partial_value"], "band": t["band"], "legal_effect_level": (t["components"]["legal_effect"]["details"] or {}).get("level")})

complete = [r for r in rows if r["state"] == "COMPLETE"]
summary = {}
for name in WEIGHTINGS:
    scores = [r["by_weighting"][name] for r in complete]
    bands = Counter(fp._band(s, fp._config(fp.TLDS_CONFIG)["bands"]) for s in scores)
    summary[name] = {"weights": WEIGHTINGS[name] or fp._config(fp.TLDS_CONFIG)["weights"], "median": round(statistics.median(scores), 1),
                     "min": round(min(scores), 1), "max": round(max(scores), 1), "bands": dict(sorted(bands.items())),
                     "spearman_vs_default": round(spearman(scores, [r["by_weighting"]["default"] for r in complete]), 3),
                     "legal_effect_material_but_band_low": sum(1 for r, s in zip(complete, scores) if r["components"]["legal_effect"] >= 0.5
                                                               and fp._band(s, fp._config(fp.TLDS_CONFIG)["bands"]) in {"Very low", "Low"})}
out = {"schema_version": "1.0.0", "method": f"{fp.TLDS_VERSION} over the 86 transitions of heldout_transitions.v2.json; offline, no model",
       "states": dict(Counter(r["state"] for r in rows)), "missing_components": dict(Counter(m for r in rows for m in r["missing"])),
       "component_medians_complete": {n: round(statistics.median(r["components"][n] for r in complete), 4) for n in fp.TLDS_COMPONENTS},
       "legal_effect_levels": dict(Counter(r["legal_effect_level"] for r in complete)),
       "weightings": summary, "invariant_violations": violations, "rows": rows,
       "note": ("Weight sensitivity on the same inputs; the bands are provisional and there are no expert labels, so no weighting is shown to be "
                "more correct. S uses the deterministic feature-hash stand-in. Legal validation: UNVERIFIED.")}
Path("reports/fingerprint/tlds_heldout.v1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, indent=1))
