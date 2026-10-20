"""Regenerate frontend/src/__tests__/fixtures/rag_answer_v5.json from the real backend.

Offline: no live India Code and no model, except 'timeout', which uses a real local socket that accepts and never answers.
Run from the repository root:
    TLD_LIVE_INDIA_CODE=0 TLD_RAG_PROVIDER=openai_compatible TLD_RAG_API_KEY= OPENAI_API_KEY= TLD_RULE_DELTA_LLM=0 \
    PYTHONPATH=src python frontend/scripts/generate_answer_fixture.py
"""

import json
import os
import socket
import threading
from pathlib import Path

from temporal_legal_drift.rag.audit import offline_extractive
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

IT19 = "Compare Section 19 before and after the IT Amendment Act, 2008."
DM31 = "How often must the district disaster management plan be reviewed under section 31 of the Disaster Management Act after the 2025 amendment?"
IBC99 = "Compare section 99 of the Insolvency and Bankruptcy Code before and after the 2026 amendment."
GENERAL = "What does the Consumer Protection Act say about mediation?"
CASES = {  # key: (question, mode, scenario, chosen section)
    "general": (GENERAL, "generic", None, None),
    "out-of-scope": ("What does section 5 of the Shops and Commercial Establishments Act require?", "specific", None, None),
    "it-s19": (IT19, "specific", None, None), "it-s19-generic": (IT19, "generic", None, None),
    "sra": ("Is specific performance of a contract still discretionary under section 11 of the Specific Relief Act after the 2018 amendment?", "specific", None, None),
    "dm31": (DM31, "specific", None, None), "dm31-month18": (DM31, "specific", {"facts": {"elapsed_months": 18}}, None),
    "dm31-month6": (DM31, "specific", {"facts": {"elapsed_months": 6}}, None),
    "ibc99": (IBC99, "specific", None, None), "ibc99-day15": (IBC99, "specific", {"facts": {"elapsed_days": 15}}, None),
    "ibc99-day25": (IBC99, "specific", {"facts": {"elapsed_days": 25}}, None),
    "mv173": ("What amount must be deposited under section 173 of the Motor Vehicles Act after the 2019 amendment?", "specific", None, None),
    "ibc240": ("Compare section 240 of the Insolvency Bankruptcy Code before and after the Insolvency And Bankruptcy Code (Amendment) Act, 2020.", "specific", None, None),
    "mv170": ("Compare section 170 of the Motor Vehicles Act before and after the Motor Vehicles (Amendment) Act, 2019.", "specific", None, None),
    "wrong-act": ("Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023.", "specific", None, None),
    "ocr": ("What changed in the IT Act amendment regarding data privacy?", "specific", None, None),
    "mv-act": ("What changed in the Motor Vehicles Act?", "specific", None, None),
    "mv-act-194": ("What changed in the Motor Vehicles Act?", "specific", None, "194"),
    "ibc-act-2025": ("What changed in the Insolvency and Bankruptcy Code after the 2025 amendment?", "specific", None, None),
    "ibc99-2025": ("Compare section 99 of the Insolvency and Bankruptcy Code before and after the 2025 amendment.", "specific", None, None),
    "unknown-act": ("What changed in the Banking Laws (Amendment) Act, 2025?", "specific", None, None),
}

root = Path(".")
out = {}
with offline_extractive():
    pipeline = RagPipeline(root)
    for key, (question, mode, scenario, section) in CASES.items():
        out[key] = pipeline.answer(question, mode, scenario=scenario, section=section)
# A real timeout: a local socket that accepts and never answers, with a 2-second limit.
server = socket.socket()
server.bind(("127.0.0.1", 0))
server.listen(5)
held = []
threading.Thread(target=lambda: [held.append(server.accept()) for _ in range(5)], daemon=True).start()
os.environ.update({"TLD_RAG_PROVIDER": "ollama", "TLD_RAG_API_URL": f"http://127.0.0.1:{server.getsockname()[1]}/api/chat",
                   "TLD_RAG_TIMEOUT_SECONDS": "2", "TLD_LIVE_INDIA_CODE": "0"})
out["timeout"] = RagPipeline(root).answer(GENERAL, "generic")
Path("frontend/src/__tests__/fixtures/rag_answer_v5.json").write_text(json.dumps({
    "_note": "Generated offline from the backend (rag-answer-v5) by frontend/scripts/generate_answer_fixture.py; 'timeout' used a real local socket that never answers (2 s limit).",
    "responses": out}, ensure_ascii=False, indent=1) + "\n")
for key, response in out.items():
    print(key, response["answer"].get("generation_method"), (response.get("fingerprint") or {}).get("tlds", {}).get("label"))
