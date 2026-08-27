"""Documented text normalization primitives."""

from __future__ import annotations

import re
import unicodedata


INLINE_SPACE = re.compile(r"[ \t\f\v]+")


def normalize_line_endings(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def normalize_block_text(value: str) -> str:
    value = normalize_line_endings(value)
    value = unicodedata.normalize("NFC", value)
    lines = [INLINE_SPACE.sub(" ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line).strip()

