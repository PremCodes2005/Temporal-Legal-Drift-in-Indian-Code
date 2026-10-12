# ADR 0004 — Local retrieval with optional live and model paths

Status: **documented existing implementation**, not a reconstructed historical approval. Audit base: `6803087`.

## Observed decision

`src/temporal_legal_drift/rag/retriever.py` builds a persistent local hybrid index from deterministic 256-dimensional feature hashes, token overlap, and legal metadata; optional Chroma storage does not change the API. `rag/rag_pipeline.py` merges optional live India Code section results, selects evidence, uses low-temperature Ollama/OpenAI-compatible generation when configured, and falls back to extractive output on model failure. The UI calls the single-prompt `/api/rag/query` endpoint (`webapp/server.py`, `frontend/src/App.jsx`).

## Consequence and boundary

The application can function without a pretrained embedding service or LLM, but the fallback is not equivalent to a legal opinion. **Inference:** local defaults favor low setup cost; no performance comparison establishing this choice was found. Retrieved current-law sections are not automatically valid historical pre/post pairs, and model/provider availability was not checked in this audit.
