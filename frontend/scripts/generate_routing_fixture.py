"""Regenerate frontend/src/__tests__/fixtures/rag_answer_v6_routing.json from the real backend (rag-answer-v6 routes).

Offline: no live India Code and no model. The latest-records cases read this machine's monitoring ledger (data/monitoring,
not versioned), so they are a snapshot of what had been observed when the fixture was made.
Run from the repository root:
    PYTHONPATH=src python frontend/scripts/generate_routing_fixture.py
"""

import json
from pathlib import Path

from temporal_legal_drift.rag.audit import offline_extractive
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

RPA = "What does the Representation of the People Act say about disqualification?"
CASES = {  # key: (question, chosen Act)
    "overview": ("What does the Motor Vehicles Act generally cover?", None),
    "named": ("What does the IT Act say about data protection?", None),
    "ambiguous": (RPA, None),
    "chosen": (RPA, "representation-of-the-people-act-1951"),
    "not-found": ("What does the Compnies Act say about directors?", None),
    "comparison": ("Compare the Aadhaar Act and the IT Act on data protection.", None),
    "mismatch": ("What did the Jan Vishwas Act change in the Motor Vehicles Act?", None),
    "latest-india-code": ("What are the latest changes in India Code?", None),
    "latest-egazette": ("What has appeared recently in the e-Gazette?", None),
    "outside": ("What is the capital of France?", None),
}

out = {}
with offline_extractive():
    pipeline = RagPipeline(Path("."))
    for key, (question, act) in CASES.items():
        out[key] = pipeline.answer(question, "specific", act=act)
Path("frontend/src/__tests__/fixtures/rag_answer_v6_routing.json").write_text(json.dumps({
    "_note": "Generated offline from the backend (rag-answer-v6) by frontend/scripts/generate_routing_fixture.py.",
    "responses": out}, ensure_ascii=False, indent=1) + "\n")
