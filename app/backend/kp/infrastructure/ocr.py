"""Local OCR: PaddleOCR models on ONNX Runtime, bundled in the package, so no download at runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OcrLine:
    text: str
    score: float
    x: float
    y: float
    height: float


def reading_order(lines: list[OcrLine]) -> list[OcrLine]:
    """Sort top to bottom, then left to right, treating vertically overlapping lines as one row."""
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda item: item.y):
        if rows and abs(line.y - rows[-1][0].y) < rows[-1][0].height * 0.6:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [line for row in rows for line in sorted(row, key=lambda item: item.x)]


class RapidOcrEngine:
    """Loads the models on first use, which takes about a second and most API requests never need."""

    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score
        self._engine = None

    def _load(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise RuntimeError("OCR_PROVIDER=RAPIDOCR requires: pip install '.[ocr]'") from exc
            self._engine = RapidOCR()
        return self._engine

    def read(self, png: bytes) -> list[OcrLine]:
        result, _ = self._load()(png)
        lines = []
        for box, text, score in result or []:
            ys = [point[1] for point in box]
            lines.append(
                OcrLine(
                    text=str(text),
                    score=float(score),
                    x=float(box[0][0]),
                    y=float(min(ys)),
                    height=float(max(ys) - min(ys)),
                )
            )
        return reading_order([line for line in lines if line.score >= self.min_score])
