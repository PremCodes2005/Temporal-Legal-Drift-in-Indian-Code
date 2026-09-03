"""Persistent deterministic embeddings and hybrid retrieval for legal text."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from temporal_legal_drift.jsonio import canonical_json_bytes, load_json
from .indiacode import INDIA_CODE_HOME, is_india_code_url


TOKEN_RE = re.compile(r"[a-z][a-z0-9]+|\d+(?:\.\d+)?", re.IGNORECASE)
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
SECTION_RE = re.compile(r"\b(?:section|sections|sec\.?|s\.)\s*(\d+[A-Za-z]?)", re.IGNORECASE)
EMBEDDING_DIMENSIONS = 256
INDEX_SCHEMA_VERSION = "1.2.0"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "of", "on", "or", "that", "the", "this", "to", "was",
    "were", "what", "which", "with", "under", "regarding", "about", "say", "does",
}
QUERY_EXPANSIONS = {
    "privacy": ("privacy", "personal", "data", "confidentiality", "disclosure"),
    "penalty": ("penalty", "fine", "imprisonment", "punishable", "liable"),
    "deadline": ("deadline", "days", "months", "within", "period"),
    "signature": ("signature", "certificate", "authentication", "electronic", "digital"),
}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    semantic_score: float
    lexical_score: float
    metadata: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": round(self.score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "metadata": self.metadata,
        }


class HybridRetriever:
    """Build and query an auditable local vector index.

    Dense vectors use stable feature hashing so the project works without a
    model download. Set ``TLD_VECTOR_BACKEND=chroma`` in a deployment with the
    optional Chroma dependency to replace storage while preserving this API.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.index_path = self.root / "data/runtime/rag_index.v1.json"
        self._document: dict[str, object] | None = None
        self.backend = os.environ.get("TLD_VECTOR_BACKEND", "local").strip().lower()
        if self.backend not in {"local", "chroma"}:
            raise ValueError("TLD_VECTOR_BACKEND must be local or chroma")

    def status(self) -> dict[str, object]:
        document = self.ensure_index()
        return {
            "ready": bool(document.get("chunks")),
            "document_count": document.get("document_count", 0),
            "chunk_count": len(document.get("chunks", [])),
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "vector_backend": "chromadb" if self.backend == "chroma" else "local_persistent_cosine",
            "hybrid_search": True,
            "index_fingerprint": document.get("corpus_fingerprint"),
            "official_repository": INDIA_CODE_HOME,
            "metadata_fields": ["document_type", "version", "act_name", "date"],
        }

    @staticmethod
    def embed_text(value: str) -> list[float]:
        """Expose the same embedding transform used by the stored index."""
        return _embedding(_tokens(value))

    def rebuild(self) -> dict[str, object]:
        self._document = self._build_index()
        self._persist(self._document)
        if self.backend == "chroma":
            self._sync_chroma(self._document)
        return self.status()

    def ensure_index(self) -> dict[str, object]:
        if self._document is not None:
            return self._document
        fingerprint = self._corpus_fingerprint()
        if self.index_path.is_file():
            try:
                existing = load_json(self.index_path)
                if (
                    existing.get("schema_version") == INDEX_SCHEMA_VERSION
                    and existing.get("corpus_fingerprint") == fingerprint
                ):
                    self._document = existing
                    if self.backend == "chroma" and self._chroma_collection().count() == 0:
                        self._sync_chroma(existing)
                    return existing
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        return self.rebuild_document(fingerprint)

    def rebuild_document(self, fingerprint: str | None = None) -> dict[str, object]:
        self._document = self._build_index(fingerprint)
        self._persist(self._document)
        if self.backend == "chroma":
            self._sync_chroma(self._document)
        return self._document

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        entry_ids: set[str] | None = None,
    ) -> list[RetrievedChunk]:
        cleaned = " ".join(str(query).split())
        if not cleaned:
            raise ValueError("query is required")
        document = self.ensure_index()
        query_tokens = _expanded_tokens(cleaned)
        query_vector = _embedding(query_tokens)
        section_match = SECTION_RE.search(cleaned)
        requested_section = section_match.group(1).lower() if section_match else None
        results: list[RetrievedChunk] = []
        candidates = (
            self._chroma_candidates(query_vector, entry_ids, max(100, limit * 8))
            if self.backend == "chroma"
            else document.get("chunks", [])
        )
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text", ""))
            metadata = dict(raw.get("metadata", {}))
            if entry_ids is not None and str(metadata.get("entry_id")) not in entry_ids:
                continue
            semantic = _cosine(query_vector, raw.get("embedding", []))
            text_tokens = set(_tokens(text))
            lexical = len(set(query_tokens) & text_tokens) / max(1, len(set(query_tokens)))
            metadata_tokens = set(_tokens(" ".join(str(metadata.get(key, "")) for key in ("act_name", "document_type", "version"))))
            metadata_match = len(set(query_tokens) & metadata_tokens) / max(1, len(set(query_tokens)))
            lowered_query = cleaned.lower()
            entry_id = str(metadata.get("entry_id", ""))
            act_bonus = 0.22 if ("it act" in lowered_query or "information technology" in lowered_query) and entry_id.startswith("it-") else 0.0
            primary_sections = set(metadata.get("primary_sections", []))
            all_sections = set(metadata.get("sections", []))
            section_bonus = 0.30 if requested_section and requested_section in primary_sections else 0.08 if requested_section and requested_section in all_sections else 0.0
            if lexical == 0 and metadata_match == 0 and section_bonus == 0 and act_bonus == 0:
                continue
            score = min(1.0, semantic * 0.42 + lexical * 0.38 + metadata_match * 0.20 + section_bonus + act_bonus)
            if score <= 0:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=str(raw["chunk_id"]), text=text, score=score,
                    semantic_score=semantic, lexical_score=lexical, metadata=metadata,
                )
            )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[:limit]

    def _chroma_candidates(
        self, query_vector: list[float], entry_ids: set[str] | None, limit: int
    ) -> list[dict[str, object]]:
        collection = self._chroma_collection()
        where = {"entry_id": {"$in": sorted(entry_ids)}} if entry_ids else None
        response = collection.query(
            query_embeddings=[query_vector],
            n_results=min(limit, collection.count()),
            where=where,
            include=["documents", "metadatas", "embeddings"],
        )
        rows = []
        for chunk_id, text, metadata, embedding in zip(
            response.get("ids", [[]])[0],
            response.get("documents", [[]])[0],
            response.get("metadatas", [[]])[0],
            response.get("embeddings", [[]])[0],
        ):
            restored = dict(metadata or {})
            for field in ("sections", "primary_sections"):
                restored[field] = [item for item in str(restored.get(field, "")).split(",") if item]
            rows.append({"chunk_id": chunk_id, "text": text, "metadata": restored, "embedding": embedding})
        return rows

    def relation_for_results(self, results: Iterable[RetrievedChunk]) -> dict[str, str] | None:
        relations_path = self.root / "configs/versioning/instrument_relations.v1.json"
        if not relations_path.is_file():
            return None
        relations = load_json(relations_path).get("amending_instrument_targets", {})
        if not isinstance(relations, dict):
            return None
        scores: dict[str, float] = {}
        for item in results:
            entry_id = str(item.metadata.get("entry_id", ""))
            scores[entry_id] = max(scores.get(entry_id, 0.0), item.score)
        candidates = []
        for amending, target in relations.items():
            combined = scores.get(str(amending), 0.0) + scores.get(str(target), 0.0)
            if combined:
                candidates.append((combined, str(amending), str(target)))
        if not candidates:
            return None
        _, amending, target = max(candidates)
        return {"amending_entry_id": amending, "target_entry_id": target}

    def _build_index(self, fingerprint: str | None = None) -> dict[str, object]:
        corpus = load_json(self.root / "data/corpus/index.json")
        normalized_by_source: dict[str, dict[str, object]] = {}
        for path in sorted((self.root / "data/normalized").glob("*.json")):
            item = load_json(path)
            normalized_by_source[str(item.get("source_artifact_id"))] = item
        chunks: list[dict[str, object]] = []
        document_count = 0
        for entry in corpus.get("entries", []):
            if not isinstance(entry, dict):
                continue
            normalized = normalized_by_source.get(str(entry.get("source_artifact_id")))
            if not normalized:
                continue
            document_count += 1
            metadata = _document_metadata(entry)
            for block in normalized.get("blocks", []):
                if not isinstance(block, dict):
                    continue
                text = " ".join(str(block.get("normalized_text", "")).split())
                for part_number, part in enumerate(_split_text(text)):
                    sections = sorted(set(match.lower() for match in SECTION_RE.findall(part)))
                    primary_sections = _primary_sections(part)
                    chunk_key = f"{entry.get('entry_id')}\n{block.get('block_id')}\n{part_number}"
                    chunks.append({
                        "chunk_id": f"rag_{sha256(chunk_key.encode()).hexdigest()[:24]}",
                        "text": part,
                        "embedding": _embedding(_tokens(part)),
                        "metadata": {
                            **metadata,
                            "source_artifact_id": entry.get("source_artifact_id"),
                            "source_anchor": block.get("source_anchor"),
                            "block_id": block.get("block_id"),
                            "sections": sections,
                            "primary_sections": primary_sections,
                        },
                    })
        self._add_version_graph_chunks(chunks, corpus)
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "corpus_fingerprint": fingerprint or self._corpus_fingerprint(),
            "document_count": document_count,
            "embedding": {"algorithm": "stable_feature_hashing", "dimensions": EMBEDDING_DIMENSIONS},
            "chunks": chunks,
        }

    def _add_version_graph_chunks(
        self, chunks: list[dict[str, object]], corpus: dict[str, object]
    ) -> None:
        graph_path = self.root / "data/interim/version_graph.v1.json"
        if not graph_path.is_file():
            return
        graph = load_json(graph_path)
        entry_by_source = {
            str(item.get("source_artifact_id")): item
            for item in corpus.get("entries", []) if isinstance(item, dict)
        }
        lineage_by_id = {
            str(item.get("lineage_id")): item
            for item in graph.get("provision_lineages", graph.get("lineages", []))
            if isinstance(item, dict)
        }
        instrument_by_id = {
            str(item.get("instrument_id")): item
            for item in graph.get("instruments", []) if isinstance(item, dict)
        }
        for version in graph.get("provision_versions", graph.get("versions", [])):
            if not isinstance(version, dict):
                continue
            evidence = version.get("evidence", {})
            if not isinstance(evidence, dict):
                continue
            entry = entry_by_source.get(str(evidence.get("source_artifact_id")))
            lineage = lineage_by_id.get(str(version.get("lineage_id")), {})
            instrument = instrument_by_id.get(str(lineage.get("instrument_id")), {})
            if entry is None and instrument:
                entry = next((item for item in corpus.get("entries", []) if isinstance(item, dict) and item.get("entry_id") == instrument.get("corpus_entry_id")), None)
            text = " ".join(str(version.get("exact_text", "")).split())
            if not entry or not text:
                continue
            number = str(lineage.get("provision_number", "")).lower()
            metadata = {
                **_document_metadata(entry),
                "source_artifact_id": evidence.get("source_artifact_id"),
                "source_anchor": evidence.get("locator"),
                "block_id": evidence.get("block_id"),
                "sections": [number] if number else [],
                "primary_sections": [number] if number else [],
                "source_kind": "provision_version",
                "version_id": version.get("version_id"),
                "provision_path": lineage.get("canonical_path"),
            }
            chunk_key = f"version\n{version.get('version_id')}"
            chunks.append({
                "chunk_id": f"rag_{sha256(chunk_key.encode()).hexdigest()[:24]}",
                "text": text,
                "embedding": _embedding(_tokens(text)),
                "metadata": metadata,
            })
        for event in graph.get("amendment_events", []):
            if not isinstance(event, dict):
                continue
            evidence = event.get("evidence", {})
            instrument = instrument_by_id.get(str(event.get("amending_instrument_id")), {})
            entry = next((item for item in corpus.get("entries", []) if isinstance(item, dict) and item.get("entry_id") == instrument.get("corpus_entry_id")), None)
            if not isinstance(evidence, dict) or not entry:
                continue
            text = " ".join(str(evidence.get("exact_text", "")).split())
            if not text:
                source_chunk = next(
                    (
                        item for item in chunks
                        if isinstance(item.get("metadata"), dict)
                        and item["metadata"].get("block_id") == evidence.get("block_id")
                    ),
                    None,
                )
                text = str(source_chunk.get("text", "")) if source_chunk else ""
            if not text:
                continue
            path = str(event.get("target_path_text", ""))
            number = path.split(":", 1)[1].lower() if path.startswith("section:") else ""
            chunk_key = f"amendment\n{event.get('amendment_event_id')}"
            chunks.append({
                "chunk_id": f"rag_{sha256(chunk_key.encode()).hexdigest()[:24]}",
                "text": text,
                "embedding": _embedding(_tokens(text)),
                "metadata": {
                    **_document_metadata(entry),
                    "source_artifact_id": evidence.get("source_artifact_id"),
                    "source_anchor": evidence.get("locator"),
                    "block_id": evidence.get("block_id"),
                    "sections": [number] if number else [],
                    "primary_sections": [number] if number else [],
                    "source_kind": "amendment_event",
                    "amendment_event_id": event.get("amendment_event_id"),
                    "amendment_operation": event.get("operation"),
                    "provision_path": path,
                },
            })

    def _corpus_fingerprint(self) -> str:
        corpus = load_json(self.root / "data/corpus/index.json")
        evidence = [
            {"entry_id": item.get("entry_id"), "sha256": item.get("sha256")}
            for item in corpus.get("entries", []) if isinstance(item, dict)
        ]
        return sha256(canonical_json_bytes(evidence)).hexdigest()

    def _persist(self, document: dict[str, object]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_bytes(canonical_json_bytes(document))
        temporary.replace(self.index_path)

    def _chroma_collection(self):
        try:
            import chromadb  # type: ignore[import-not-found]
        except ImportError as error:
            raise ValueError(
                "ChromaDB backend requested; install the project with the 'rag' extra"
            ) from error
        client = chromadb.PersistentClient(path=str(self.root / "data/runtime/chroma"))
        return client.get_or_create_collection(
            "temporal_legal_drift_v1", metadata={"hnsw:space": "cosine"}
        )

    def _sync_chroma(self, document: dict[str, object]) -> None:
        collection = self._chroma_collection()
        existing = collection.get(include=[]).get("ids", [])
        if existing:
            collection.delete(ids=existing)
        chunks = [item for item in document.get("chunks", []) if isinstance(item, dict)]
        for start in range(0, len(chunks), 400):
            batch = chunks[start:start + 400]
            metadatas = []
            for item in batch:
                metadata = {}
                for key, value in dict(item.get("metadata", {})).items():
                    if isinstance(value, list):
                        metadata[key] = ",".join(str(part) for part in value)
                    elif value is None:
                        metadata[key] = ""
                    elif isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                metadatas.append(metadata)
            collection.add(
                ids=[str(item["chunk_id"]) for item in batch],
                documents=[str(item["text"]) for item in batch],
                embeddings=[item["embedding"] for item in batch],
                metadatas=metadatas,
            )


def _document_metadata(entry: dict[str, object]) -> dict[str, object]:
    entry_id = str(entry.get("entry_id", ""))
    year_match = YEAR_RE.search(entry_id)
    year = year_match.group(0) if year_match else None
    document_type = "amending_act" if "amendment" in entry_id else "consolidated_act" if "consolidated" in entry_id else "act_or_code"
    base = entry_id.replace("-consolidated", "")
    base = re.sub(r"-amendment-act-(?:19|20)\d{2}$", "-act", base)
    act_name = " ".join(word.upper() if word == "it" else word.title() for word in base.split("-"))
    version = f"amendment_{year}" if document_type == "amending_act" else "consolidated" if document_type == "consolidated_act" else f"published_{year}" if year else "unspecified"
    source_url = str(entry.get("parent_reference_url") or entry.get("source_url") or INDIA_CODE_HOME)
    return {
        "entry_id": entry_id,
        "filename": entry.get("filename"),
        "document_type": document_type,
        "version": version,
        "act_name": act_name,
        "date": year,
        "date_precision": "year_from_document_title" if year else "unknown",
        "official_identifier": entry.get("official_identifier"),
        "source_url": source_url,
        "source_is_india_code": is_india_code_url(source_url),
        "official_portal_url": INDIA_CODE_HOME,
    }


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value) if token.lower() not in STOPWORDS]


def _expanded_tokens(value: str) -> list[str]:
    tokens = _tokens(value)
    expanded = list(tokens)
    lowered = value.lower()
    for key, additions in QUERY_EXPANSIONS.items():
        if key in lowered:
            expanded.extend(additions)
    return expanded


def _embedding(tokens: Iterable[str]) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [round(value / magnitude, 8) for value in vector] if magnitude else vector


def _cosine(left: list[float], right: object) -> float:
    if not isinstance(right, list) or len(left) != len(right):
        return 0.0
    return max(0.0, min(1.0, sum(a * float(b) for a, b in zip(left, right))))


def _split_text(text: str, maximum: int = 2200, overlap: int = 240) -> list[str]:
    if not text:
        return []
    if len(text) <= maximum:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        end = min(len(text), start + maximum)
        if end < len(text):
            boundary = max(text.rfind(". ", start + maximum // 2, end), text.rfind("; ", start + maximum // 2, end))
            if boundary > start:
                end = boundary + 1
        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return parts


def _primary_sections(text: str) -> list[str]:
    values = re.findall(r"(?:^|\s)(\d+[A-Za-z]?)\.\s+(?=[A-Z\[])" , text[:700])
    return sorted({value.lower() for value in values})
