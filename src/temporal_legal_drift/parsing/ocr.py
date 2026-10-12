"""Frozen OCR candidates for scanned sources whose embedded text layer is unreliable.

The output is a reviewer aid with per-word confidence. It is not verified text
and does not replace the source's text layer in extraction.
"""

from __future__ import annotations

import statistics
import subprocess
from hashlib import sha256
from io import BytesIO
from pathlib import Path

TESSERACT_VERSION = "5.5.3"


def build_ocr_candidate(root: Path, entry_id: str, version: str = "v1") -> dict[str, object]:
    import pypdf

    from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

    banner = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=True).stdout
    if not banner.startswith(f"tesseract {TESSERACT_VERSION}"):
        raise RuntimeError(f"OCR candidates are pinned to tesseract {TESSERACT_VERSION}: {banner.splitlines()[0]}")
    tessdata = Path(subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, check=True)
                    .stdout.splitlines()[0].split('"')[1])
    root = root.resolve()
    item = {str(e["entry_id"]): e for e in load_json(root / "reports/corpus/india-code-temporal-pilot-v1.lock.json")["entries"]}[entry_id]
    payload = (root / "data/raw" / str(item["blob_path"])).read_bytes()
    if sha256(payload).hexdigest() != item["sha256"]:
        raise ValueError(f"raw PDF hash mismatch: {entry_id}")
    pages = []
    for number, page in enumerate(pypdf.PdfReader(BytesIO(payload)).pages, 1):
        images = page["/Resources"]["/XObject"]
        if len(images) != 1:
            raise ValueError(f"page {number}: expected one scanned page image, found {len(images)}")
        image = images[next(iter(images))].get_object()
        if image.get("/Filter") != "/DCTDecode":
            raise ValueError(f"page {number}: unsupported image encoding {image.get('/Filter')}")
        dpi = round(int(image["/Width"]) / (float(page.mediabox.width) / 72))
        command = ["tesseract", "stdin", "stdout", "--dpi", str(dpi), "-l", "eng"]
        text = subprocess.run(command, input=image._data, capture_output=True, check=True).stdout.decode()
        rows = [line.split("\t") for line in subprocess.run(
            [*command, "tsv"], input=image._data, capture_output=True, check=True).stdout.decode().splitlines()[1:]]
        confidences = [float(row[10]) for row in rows if len(row) == 12 and row[11].strip() and float(row[10]) >= 0]
        pages.append({
            "page": number,
            "image_sha256": sha256(image._data).hexdigest(),
            "dpi": dpi,
            "word_count": len(confidences),
            "mean_word_confidence": round(statistics.mean(confidences), 2) if confidences else None,
            "low_confidence_word_fraction": round(sum(c < 60 for c in confidences) / len(confidences), 4) if confidences else None,
            "text": text,
        })
    artifact = {
        "schema_version": "1.0.0",
        "ocr_version": f"tesseract-ocr-candidate-{version}",
        "entry_id": entry_id,
        "source_sha256": item["sha256"],
        "engine": {"name": "tesseract", "version": TESSERACT_VERSION, "language": "eng",
                   "eng_traineddata_sha256": sha256((tessdata / "eng.traineddata").read_bytes()).hexdigest(),
                   "page_segmentation": "default (3)", "input": "embedded page image at native resolution"},
        "status": "OCR_CANDIDATE_MANUAL_VERIFICATION_REQUIRED",
        "use_policy": "Not used for extraction or transitions; affected events stay source_text_unreliable until a reviewer verifies the text against the page images.",
        "pages": pages,
    }
    path = root / f"data/processed/ocr/{version}/{entry_id}.json"
    out = canonical_json_bytes(artifact)
    atomic_write_new(path, out)
    return {"path": str(path.relative_to(root)), "sha256": sha256(out).hexdigest(), "pages": len(pages),
            "mean_word_confidence": round(statistics.mean(p["mean_word_confidence"] for p in pages), 2)}
