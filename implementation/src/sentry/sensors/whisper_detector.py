"""Entropy-based detector for suspicious text in local SENTRY logs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for char in text:
        counts[char] = counts.get(char, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def bigram_entropy(text: str) -> float:
    if len(text) < 2:
        return 0.0
    bigrams = [text[i : i + 2] for i in range(len(text) - 1)]
    counts: dict[str, int] = {}
    for bigram in bigrams:
        counts[bigram] = counts.get(bigram, 0) + 1
    length = len(bigrams)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


@dataclass
class WhisperDetectorConfig:
    enabled: bool = True
    entropy_threshold: float = 4.5
    min_text_len: int = 80
    max_lines: int = 50
    anomaly_score: float = 0.20


@dataclass
class WhisperResult:
    score: float
    suspicious: bool
    entropy: float
    detail: str

    def flags(self) -> dict[str, Any]:
        return {
            "steganography_suspected": self.suspicious,
            "whisper_entropy": self.entropy,
            "whisper_detector_detail": self.detail,
        }


class WhisperDetector:
    """Scan local text fields for high-entropy encoded payload shapes."""

    def __init__(self, config: WhisperDetectorConfig | None = None) -> None:
        self.config = config or WhisperDetectorConfig()

    def analyse_text(self, text: str) -> WhisperResult:
        if not self.config.enabled:
            return WhisperResult(0.0, False, 0.0, "disabled")
        if len(text) < self.config.min_text_len:
            return WhisperResult(0.0, False, 0.0, f"too_short={len(text)}")

        entropy = shannon_entropy(text)
        b_entropy = bigram_entropy(text)
        whitespace_ratio = sum(1 for char in text if char.isspace()) / len(text)
        punctuation_ratio = sum(1 for char in text if not char.isalnum() and not char.isspace()) / len(text)
        encoded_shape = whitespace_ratio < 0.10 or punctuation_ratio > 0.30
        suspicious = entropy >= self.config.entropy_threshold and encoded_shape
        score = self.config.anomaly_score if suspicious else 0.0
        detail = (
            f"entropy={entropy:.3f} bigram={b_entropy:.3f} "
            f"whitespace={whitespace_ratio:.3f} punctuation={punctuation_ratio:.3f}"
        )
        return WhisperResult(score, suspicious, entropy, detail)

    def scan_texts(self, texts: Iterable[str]) -> WhisperResult:
        strongest = WhisperResult(0.0, False, 0.0, "no text")
        for text in texts:
            result = self.analyse_text(text)
            if result.score > strongest.score or result.entropy > strongest.entropy:
                strongest = result
        return strongest

    def scan_jsonl(self, path: Path) -> WhisperResult:
        if not path.exists():
            return WhisperResult(0.0, False, 0.0, "file missing")
        texts: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-self.config.max_lines :]:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            texts.extend(_extract_text_fields(obj))
        return self.scan_texts(texts)


def _extract_text_fields(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        values: list[str] = []
        for value in obj.values():
            values.extend(_extract_text_fields(value))
        return values
    if isinstance(obj, list):
        values = []
        for value in obj:
            values.extend(_extract_text_fields(value))
        return values
    return []
