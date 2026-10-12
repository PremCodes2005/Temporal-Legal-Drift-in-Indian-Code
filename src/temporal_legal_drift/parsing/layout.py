"""Layout-aware detection of Gazette page furniture from PDF text coordinates.

Source-specific to India Code / Gazette of India PDFs: a running header in the
top band, the "IndiaCode" watermark, and marginal notes in the left and right
margins outside the body text column. Each detected run keeps its page and
coordinates so a reviewer can check it against the original page.
"""

from __future__ import annotations

import re
from io import BytesIO

PYPDF_VERSION = "6.16.2"
RULES = {
    "header_band_points_from_top": 90,
    "header_line_pattern": r"GAZETTE\s*OF\s*INDIA|^\d{1,4}$",
    "footer_band_points_from_bottom": 45,
    "watermark_text": "IndiaCode",
    "body_run_min_characters": 40,
    "left_margin_points_left_of_body": 15,
    "right_margin_fraction_of_width": 0.8,
    "margin_note_min_alphanumeric_run": 2,
}
_HEADER = re.compile(RULES["header_line_pattern"], re.I)
_WORD = re.compile(r"[A-Za-z0-9]{%d,}" % RULES["margin_note_min_alphanumeric_run"])


def gazette_furniture(payload: bytes) -> list[dict[str, object]]:
    import pypdf

    if pypdf.__version__ != PYPDF_VERSION:
        raise RuntimeError(f"layout detection is pinned to pypdf {PYPDF_VERSION}, found {pypdf.__version__}")
    reader = pypdf.PdfReader(BytesIO(payload))
    results: list[dict[str, object]] = []
    for number, page in enumerate(reader.pages, 1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        runs: list[tuple[float, float, str]] = []

        def visit(text, cm, tm, font, size, runs=runs):
            if text.strip():
                runs.append((tm[4] * cm[0] + cm[4], tm[5] * cm[3] + cm[5], " ".join(text.split())))

        page.extract_text(visitor_text=visit)
        runs = [run for run in runs if (run[0], run[1]) != (0, 0)]  # position unknown: never classified
        body_starts = [x for x, _, text in runs if len(text) >= RULES["body_run_min_characters"]]
        body_left = min(body_starts) if body_starts else None
        top_lines: dict[int, list[tuple[float, str]]] = {}
        for x, y, text in runs:
            if y >= height - RULES["header_band_points_from_top"]:
                top_lines.setdefault(round(y), []).append((x, text))
        # A top-band line is a header only if it reads like one; body text can reach the band.
        header_ys = {y for y, parts in top_lines.items() if _HEADER.search("".join(t for _, t in sorted(parts)))}
        bands: dict[tuple[str, float], list[tuple[float, str]]] = {}
        for x, y, text in runs:
            zone = None
            if round(y) in header_ys:
                zone = "running_header"
            elif y <= RULES["footer_band_points_from_bottom"]:
                zone = "footer"
            elif text == RULES["watermark_text"]:
                zone = "watermark"
            elif _WORD.search(text) and body_left is not None and x < body_left - RULES["left_margin_points_left_of_body"]:
                zone = "left_margin_note"
            elif _WORD.search(text) and x >= width * RULES["right_margin_fraction_of_width"]:
                zone = "right_margin_note"
            if zone:
                results.append({"page": number, "x": round(x, 1), "y": round(y, 1), "text": text, "zone": zone})
                if zone in {"running_header", "footer"}:
                    bands.setdefault((zone, round(y)), []).append((x, text))
        # pypdf splits a header line into several runs; also record each whole band line.
        for (zone, y), parts in sorted(bands.items()):
            if len(parts) > 1:
                text = "".join(text for _, text in sorted(parts))
                results.append({"page": number, "x": round(min(parts)[0], 1), "y": float(y), "text": text, "zone": zone, "combined_runs": len(parts)})
    return results


def build_layout_furniture_artifact(root, version: str = "v1") -> dict[str, object]:
    """Freeze furniture runs for every amending Act so extraction never needs pypdf at rebuild time."""
    from hashlib import sha256
    from pathlib import Path

    from temporal_legal_drift.corpus import CorpusManifest
    from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

    root = Path(root).resolve()
    manifest = CorpusManifest.from_file(root / "configs/corpus/pilot_v1.json")
    report = {str(item["entry_id"]): item for item in load_json(root / "reports/corpus/india-code-temporal-pilot-v1.lock.json")["entries"]}
    documents = {}
    for entry in manifest.entries:
        if entry.instrument_type != "amending_act":
            continue
        item = report[entry.entry_id]
        payload = (root / "data/raw" / str(item["blob_path"])).read_bytes()
        if sha256(payload).hexdigest() != item["sha256"]:
            raise ValueError(f"raw PDF hash mismatch: {entry.entry_id}")
        documents[entry.entry_id] = {"source_sha256": item["sha256"], "runs": gazette_furniture(payload)}
    artifact = {
        "schema_version": "1.0.0",
        "layout_version": f"gazette-layout-furniture-{version}",
        "pypdf_version": PYPDF_VERSION,
        "rules": RULES,
        "scope": "Gazette of India / India Code amending-Act PDFs; a reviewer aid, not a legal finding",
        "documents": documents,
    }
    path = root / f"data/processed/layout/{version}/gazette_furniture.json"
    payload = canonical_json_bytes(artifact)
    atomic_write_new(path, payload)
    return {"path": str(path.relative_to(root)), "sha256": sha256(payload).hexdigest(),
            "documents": len(documents), "runs": sum(len(item["runs"]) for item in documents.values())}
