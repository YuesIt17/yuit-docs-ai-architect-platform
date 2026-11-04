"""Label normalize + OCR/extract for PDF/PNG/JPEG/WEBP/TIFF. OCR text is untrusted input."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image

from kp.config import Settings
from kp.infrastructure.ocr import RapidOcrEngine
from kp.security.guardrails import sanitize_pii


@dataclass
class VisionResult:
    source_format: str
    page_count: int
    page_images_png: list[bytes]
    ocr_text: str
    brand: str | None
    barcode: str | None
    net_weight: str | None
    ingredients: str | None
    allergens: list[str]
    confidence: float
    provider: str = "MOCK"


ALLERGEN_LEXICON = [
    "gluten",
    "wheat",
    "milk",
    "lactose",
    "egg",
    "soy",
    "peanut",
    "nut",
    "fish",
    "shellfish",
    "celery",
    "mustard",
    "sesame",
    "sulfite",
]
# A line starting with one of these ends a multi-line ingredients block.
_NEXT_FIELD = re.compile(
    r"^(?:brand|barcode|net\s*weight|contains|allergen|may\s+contain|best\s+before|store|nutrition)\b", re.I
)


class VisionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.ocr_provider.upper()
        if self.provider not in {"MOCK", "RAPIDOCR"}:
            raise RuntimeError(
                f"Unknown OCR_PROVIDER={settings.ocr_provider!r}. Use MOCK or RAPIDOCR. Refusing silent mock fallback."
            )
        self._ocr = RapidOcrEngine() if self.provider == "RAPIDOCR" else None

    def _read_pages(self, pages: list[bytes]) -> tuple[str, float]:
        """Return page text and the mean recognition score, which is 0.0 when nothing was read."""
        lines = [line for page in pages for line in self._ocr.read(page)]
        if not lines:
            return "", 0.0
        return "\n".join(line.text for line in lines), sum(line.score for line in lines) / len(lines)

    def detect_format(self, filename: str, data: bytes) -> str:
        name = filename.lower()
        if data.startswith(b"%PDF"):
            return "pdf"
        if data.startswith(b"\x89PNG"):
            return "png"
        if data.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
            return "tiff"
        ext = name.rsplit(".", 1)[-1]
        return {"jpg": "jpeg", "tif": "tiff"}.get(ext, ext)

    def normalize(self, filename: str, data: bytes, page_limit: int = 3) -> tuple[str, list[bytes]]:
        fmt = self.detect_format(filename, data)
        if data.startswith(b"%PDF-TEXT") or (not data.startswith(b"%PDF") and self._looks_like_text(data)):
            return fmt if fmt in {"pdf", "png", "jpeg", "webp", "tiff"} else "png", []
        pages: list[bytes] = []
        if fmt == "pdf":
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(data)
            n = min(len(pdf), page_limit)
            for i in range(n):
                page = pdf[i]
                pil = page.render(scale=2).to_pil()
                buf = io.BytesIO()
                pil.convert("RGB").save(buf, format="PNG")
                pages.append(buf.getvalue())
            return fmt, pages
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            return fmt, []
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return fmt, [buf.getvalue()]

    @staticmethod
    def _looks_like_text(data: bytes) -> bool:
        try:
            sample = data[:200].decode("utf-8")
        except UnicodeDecodeError:
            return False
        return any(k in sample for k in ("Brand:", "Ingredients:", "Allergen"))

    def _mock_ocr_from_bytes(self, filename: str, data: bytes, pages: list[bytes]) -> str:
        try:
            text = data.decode("utf-8")
            if "Ingredients" in text or "allerg" in text.lower():
                return text
        except UnicodeDecodeError:
            pass
        lower = filename.lower()
        if "secret" in lower:
            return (
                "Brand: PrivateLabelX\nBarcode: 4601234567890\n"
                "Ingredients: water, sugar, milk powder, gluten\n"
                "Allergens: milk, gluten\nNet weight: 500g\n"
                "INTERNAL MARGIN NOTE: promo margin 42%"
            )
        if "label" in lower or pages:
            return (
                "Brand: FreshFarm\nBarcode: 4609876543210\n"
                "Ingredients: oats, honey, almonds, salt\n"
                "Contains allergens: gluten, nuts\n"
                "Allergen advice: may contain milk\nNet weight: 400g"
            )
        return "Brand: Unknown\nIngredients: n/a"

    def extract_structured(self, ocr_text: str) -> dict:
        brand = None
        m = re.search(r"Brand:\s*(.+)", ocr_text, re.I)
        if m:
            brand = m.group(1).strip()
        barcode = None
        # OCR confuses letters and digits in the field name, so a standalone EAN/UPC length also counts.
        m = re.search(r"Barc[o0]de:\s*(\d+)", ocr_text, re.I) or re.search(r"\b(\d{13}|\d{12}|\d{8})\b", ocr_text)
        if m:
            barcode = m.group(1)
        net_weight = None
        m = re.search(r"Net weight:\s*(.+)", ocr_text, re.I)
        if m:
            net_weight = m.group(1).strip()
        ingredients = None
        m = re.search(r"Ingredients:\s*(.+)", ocr_text, re.I)
        if m:
            ingredients = m.group(1).strip()
            for line in ocr_text[m.end() :].splitlines()[1:]:
                if not line.strip() or _NEXT_FIELD.match(line.strip()):
                    break
                ingredients = f"{ingredients} {line.strip()}"
        allergens: list[str] = []
        low = ocr_text.lower()
        for a in ALLERGEN_LEXICON:
            # Whole words: "peanut" and "doughnut" must not report the "nut" allergen.
            if re.search(rf"\b{a}s?\b", low):
                allergens.append(a)
        seen: set[str] = set()
        allergens = [x for x in allergens if not (x in seen or seen.add(x))]
        return {
            "brand": brand,
            "barcode": barcode,
            "net_weight": net_weight,
            "ingredients": ingredients,
            "allergens": allergens,
            "confidence": 0.82 if allergens or brand else 0.4,
            "raw_ocr_text": ocr_text,
        }

    def recognize(self, filename: str, data: bytes, page_limit: int = 3) -> VisionResult:
        fmt, pages = self.normalize(filename, data, page_limit=page_limit)
        score = None
        if not self.settings.enable_vision_ocr:
            ocr_text = ""
        elif self.provider == "RAPIDOCR":
            ocr_text, score = self._read_pages(pages)
        else:
            ocr_text = self._mock_ocr_from_bytes(filename, data, pages)
        ocr_text = sanitize_pii(ocr_text)
        structured = self.extract_structured(ocr_text)
        return VisionResult(
            source_format=fmt,
            page_count=len(pages),
            page_images_png=pages,
            ocr_text=ocr_text,
            brand=structured["brand"],
            barcode=structured["barcode"],
            net_weight=structured["net_weight"],
            ingredients=structured["ingredients"],
            allergens=structured["allergens"],
            confidence=structured["confidence"] if score is None else score,
            provider=self.provider,
        )
