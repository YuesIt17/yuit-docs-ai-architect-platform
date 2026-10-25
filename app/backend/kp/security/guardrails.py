"""Input/Output guardrails (hw-6 evolution)."""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s*prompt",
    r"jailbreak",
    r"reveal\s+secret",
    r"игнорируй\s+(все\s+)?(предыдущие|приор)",
    r"покажи\s+системн",
]

PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{3}-\d{3}\s*\d{2}\b"), "[INN_REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)"), "[PHONE_REDACTED]"),
]


@dataclass
class GuardResult:
    ok: bool
    text: str
    reasons: list[str]


def sanitize_pii(text: str) -> str:
    out = text
    for pattern, repl in PII_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def input_guard(text: str) -> GuardResult:
    reasons: list[str] = []
    lowered = text.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lowered, flags=re.IGNORECASE):
            reasons.append(f"prompt_injection:{pat}")
    cleaned = sanitize_pii(text)
    if reasons:
        return GuardResult(ok=False, text=cleaned, reasons=reasons)
    return GuardResult(ok=True, text=cleaned, reasons=[])


def output_guard(
    answer: str,
    citations: list[dict],
    principal_role: str,
    retrieved_classifications: list[str],
) -> GuardResult:
    reasons: list[str] = []
    if "secret" in retrieved_classifications and principal_role != "compliance_officer":
        reasons.append("acl_leak_blocked")
        return GuardResult(
            ok=False,
            text="Access denied: retrieved context includes classified material outside your clearance.",
            reasons=reasons,
        )
    # Prefer grounded answers for knowledge questions
    if not citations and len(answer) > 40 and "недостаточно" not in answer.lower():
        # soft warning — still allow OCR-only / degrade paths
        reasons.append("no_citations")
    return GuardResult(ok=True, text=sanitize_pii(answer), reasons=reasons)


ALLOWED_LABEL_MIME = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/tiff",
    "application/pdf",
}

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 10

# Magic-byte hints (not full format validation).
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"%PDF", "pdf"),
    (b"RIFF", "webp"),  # WEBP is RIFF....WEBP
]


def sniff_image_or_pdf(data: bytes) -> str | None:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    for magic, kind in _SIGNATURES:
        if data.startswith(magic):
            return kind
    # TIFF little/big endian
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    return None


def vision_input_guard(
    filename: str,
    content_type: str | None,
    size: int,
    data: bytes | None = None,
    *,
    allow_text_fixtures: bool = False,
) -> GuardResult:
    reasons: list[str] = []
    if size > MAX_UPLOAD_BYTES:
        reasons.append("file_too_large")
    # Reject path traversal / absolute names in the declared filename.
    lowered_name = (filename or "").replace("\\", "/")
    if lowered_name.startswith("/") or ".." in lowered_name.split("/"):
        reasons.append("unsafe_filename")
    ct = (content_type or "").split(";")[0].strip().lower()
    base = lowered_name.split("/")[-1]
    ext = base.lower().rsplit(".", 1)[-1] if "." in base else ""
    ok_ext = ext in {"png", "jpg", "jpeg", "webp", "tif", "tiff", "pdf"}
    if ct and ct not in ALLOWED_LABEL_MIME and not ok_ext:
        reasons.append(f"mime_not_allowed:{ct}")
    if not ok_ext and ct not in ALLOWED_LABEL_MIME:
        reasons.append("extension_not_allowed")
    if data is not None and len(data) > 0:
        sniffed = sniff_image_or_pdf(data)
        if sniffed is None:
            # Text/mock OCR fixtures (deterministic demo) only when explicitly allowed.
            looks_text = False
            try:
                sample = data[:2048]
                sample.decode("utf-8")
                looks_text = b"\x00" not in sample
            except UnicodeDecodeError:
                looks_text = False
            if allow_text_fixtures and looks_text:
                pass
            else:
                reasons.append("content_signature_mismatch")
        elif ok_ext:
            ext_norm = "jpg" if ext in {"jpg", "jpeg"} else ("tiff" if ext == "tif" else ext)
            sniff_norm = sniffed
            if ext_norm != sniff_norm:
                reasons.append("mime_ext_signature_mismatch")
    if reasons:
        return GuardResult(ok=False, text="", reasons=reasons)
    return GuardResult(ok=True, text=filename, reasons=[])
