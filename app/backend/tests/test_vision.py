from pathlib import Path

from app.config import get_settings
from app.services.vision import VisionService


def test_recognize_text_fixture_as_png():
    settings = get_settings()
    vs = VisionService(settings)
    fixture = Path(__file__).resolve().parents[2] / "datasets" / "fixtures" / "label.png.txt"
    data = fixture.read_bytes()
    result = vs.recognize("label.png", data)
    assert result.source_format in {"png", "txt"} or result.allergens
    assert "gluten" in result.allergens or "nuts" in result.allergens
    assert result.brand == "FreshFarm"
