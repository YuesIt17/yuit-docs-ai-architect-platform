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


def vision_input_guard(filename: str, content_type: str | None, size: int) -> GuardResult:
    reasons: list[str] = []
    if size > MAX_UPLOAD_BYTES:
        reasons.append("file_too_large")
    ct = (content_type or "").split(";")[0].strip().lower()
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    ok_ext = ext in {"png", "jpg", "jpeg", "webp", "tif", "tiff", "pdf"}
    if ct and ct not in ALLOWED_LABEL_MIME and not ok_ext:
        reasons.append(f"mime_not_allowed:{ct}")
    if not ok_ext and ct not in ALLOWED_LABEL_MIME:
        reasons.append("extension_not_allowed")
    if reasons:
        return GuardResult(ok=False, text="", reasons=reasons)
    return GuardResult(ok=True, text=filename, reasons=[])
