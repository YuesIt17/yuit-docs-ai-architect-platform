"""Real OCR on a generated label, plus extraction rules that apply to any OCR provider."""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from kp.config import Settings
from kp.infrastructure.ocr import OcrLine, reading_order
from kp.infrastructure.vision import VisionService


def line(text: str, x: float, y: float) -> OcrLine:
    return OcrLine(text=text, score=0.9, x=x, y=y, height=30)


def label_png() -> bytes:
    """A label whose blocks are not in simple top-to-bottom, full-width order."""
    font = ImageFont.load_default(size=36)
    image = Image.new("RGB", (1100, 640), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 40), "Brand: NordicGrain", font=font, fill="black")
    draw.text((680, 45), "Net weight: 350g", font=font, fill="black")
    draw.text((60, 150), "Ingredients: oat flakes, wheat flour,", font=font, fill="black")
    draw.text((60, 200), "sesame seeds, sea salt", font=font, fill="black")
    draw.text((60, 310), "Contains allergens: gluten, sesame", font=font, fill="black")
    draw.text((640, 530), "Barcode: 4001234567891", font=font, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_reading_order_keeps_same_row_blocks_together():
    lines = [line("Net weight: 350g", 640, 45), line("Ingredients: oats", 60, 140), line("Brand: X", 60, 40)]
    assert [item.text for item in reading_order(lines)] == ["Brand: X", "Net weight: 350g", "Ingredients: oats"]


def test_ingredients_continue_across_lines_until_the_next_field():
    extract = VisionService(Settings()).extract_structured(
        "Brand: X\nIngredients: oat flakes, wheat flour,\nsesame seeds, sea salt\nContains allergens: gluten"
    )
    assert extract["ingredients"] == "oat flakes, wheat flour, sesame seeds, sea salt"


def test_barcode_survives_ocr_confusing_letters_and_digits():
    service = VisionService(Settings())
    assert service.extract_structured("Barc0de: 4001234567891")["barcode"] == "4001234567891"
    assert service.extract_structured("8ARCODE 4001234567891")["barcode"] == "4001234567891"
    assert service.extract_structured("Net weight: 350g")["barcode"] is None


def test_allergens_match_whole_words():
    extract = VisionService(Settings()).extract_structured("Ingredients: peanut oil, doughnut flavor, eggs")
    assert "peanut" in extract["allergens"]
    assert "egg" in extract["allergens"]
    assert "nut" not in extract["allergens"]


def test_unknown_provider_is_rejected_rather_than_mocked():
    with pytest.raises(RuntimeError, match="OCR_PROVIDER"):
        VisionService(Settings(ocr_provider="TESSERACT"))


def test_mock_provider_is_reported_as_mock():
    result = VisionService(Settings()).recognize("label.png", label_png())
    assert result.provider == "MOCK"


def test_real_ocr_reads_the_label_not_the_filename():
    pytest.importorskip("rapidocr_onnxruntime")
    # The mock would answer "FreshFarm" for this filename, so this proves the pixels were read.
    result = VisionService(Settings(ocr_provider="RAPIDOCR")).recognize("label.png", label_png())
    assert result.provider == "RAPIDOCR"
    assert result.brand == "NordicGrain"
    assert result.barcode == "4001234567891"
    assert "350g" in (result.net_weight or "")
    assert "sesame seeds" in (result.ingredients or "")
    assert {"gluten", "sesame", "wheat"} <= set(result.allergens)
    assert 0.5 < result.confidence <= 1.0


def test_real_ocr_on_a_blank_image_has_no_confidence():
    pytest.importorskip("rapidocr_onnxruntime")
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, format="PNG")
    result = VisionService(Settings(ocr_provider="RAPIDOCR")).recognize("label.png", buffer.getvalue())
    assert result.ocr_text == ""
    assert result.confidence == 0.0
