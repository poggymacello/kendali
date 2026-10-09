"""Deterministic security detectors. None of these rely on the LLM.

* prompt-injection / instruction smuggling inside untrusted documents
* hidden characters (zero-width, bidi overrides) and homoglyph impersonation
* social-engineering pressure ("urgent", "new bank details")
* address poisoning (look-alike addresses) and blocklist screening
"""

from __future__ import annotations

import re
import unicodedata

from .models import Finding, Severity

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|policies|prompts?)",
    r"(disregard|override|bypass|skip)\s+(the\s+|all\s+|your\s+)?(policy|policies|limits?|rules|guardrails?|checks?|approval)",
    r"\b(system|assistant|developer)\s*(prompt)?\s*:",
    r"<\s*/?\s*(system|instructions?|prompt)\s*>",
    r"you\s+are\s+(now\s+)?(an?\s+|the\s+)?(ai|assistant|agent|payment\s+bot)",
    r"(dear|attention|note\s+to(\s+the)?)\s+(ai|assistant|agent|bot|llm)",
    r"do\s+not\s+(tell|inform|notify|alert)\s+(the\s+)?(owner|human|user|finance|treasurer)",
    r"(approve|execute|process)\s+(this|the)\s+(payment|transfer|invoice)\s+(automatically|immediately|without)",
    r"new\s+instructions?\s*:",
    # Bahasa Indonesia
    r"abaikan\s+(semua\s+)?(instruksi|aturan|perintah|kebijakan)",
    r"kamu\s+(sekarang\s+)?adalah\s+(ai|asisten|agen)",
    r"jangan\s+(beritahu|kasih\s+tahu|laporkan)\s+(ke\s+)?(pemilik|owner|atasan)",
    r"(langsung|otomatis)\s+(bayar|transfer|setujui)\s+tanpa",
]

PRESSURE_PATTERNS = [
    r"\burgent(ly)?\b",
    r"\bimmediately\b",
    r"within\s+\d+\s+(hour|hours|minutes)",
    r"(account|service)\s+will\s+be\s+(suspended|terminated|closed)",
    r"(changed|updated|new)\s+(our\s+)?(bank|payment|wallet|account)\s+(details|information|address)",
    r"\bsegera\b",
    r"hari\s+ini\s+juga",
    r"(rekening|wallet|alamat)\s+(baru|kami\s+berubah)",
    r"\bdenda\b",
]

HIDDEN_CHARS = {
    "​": "ZERO WIDTH SPACE",
    "‌": "ZERO WIDTH NON-JOINER",
    "‍": "ZERO WIDTH JOINER",
    "⁠": "WORD JOINER",
    "﻿": "ZERO WIDTH NO-BREAK SPACE",
    "‪": "LRE",
    "‫": "RLE",
    "‬": "PDF",
    "‭": "LRO",
    "‮": "RLO",
    "⁦": "LRI",
    "⁧": "RLI",
    "⁨": "FSI",
    "⁩": "PDI",
}

# Minimal confusables map (Cyrillic/Greek letters that render like Latin ones).
CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j",
    "ѕ": "s", "к": "k", "м": "m", "т": "t", "н": "h", "в": "b",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "У": "Y", "І": "I",
    "ο": "o", "α": "a", "ν": "v", "ρ": "p", "τ": "t", "Ο": "O", "Α": "A", "Β": "B", "Ε": "E",
    "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ρ": "P", "Τ": "T", "Χ": "X",
}

ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")
BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")


def strip_hidden(text: str) -> tuple[str, list[str]]:
    found = sorted({name for ch, name in HIDDEN_CHARS.items() if ch in text})
    cleaned = "".join(ch for ch in text if ch not in HIDDEN_CHARS)
    return cleaned, found


def fold_confusables(text: str) -> tuple[str, bool]:
    """Map look-alike non-Latin letters to Latin; report whether any were present."""
    changed = False
    out = []
    for ch in unicodedata.normalize("NFKC", text):
        if ch in CONFUSABLES:
            out.append(CONFUSABLES[ch])
            changed = True
        else:
            out.append(ch)
    return "".join(out), changed


def scan_document(text: str) -> list[Finding]:
    """Scan an untrusted document (invoice, email, chat) for manipulation attempts."""
    findings: list[Finding] = []
    cleaned, hidden = strip_hidden(text)
    if hidden:
        findings.append(
            Finding(
                code="HIDDEN_CHARACTERS",
                severity=Severity.HIGH,
                message="Document contains invisible or direction-override characters often used to hide content.",
                evidence={"characters": hidden},
            )
        )
    lower = cleaned.lower()
    hits = [p for p in INJECTION_PATTERNS if re.search(p, lower)]
    if hits:
        snippet = ""
        m = re.search(hits[0], lower)
        if m:
            start = max(0, m.start() - 40)
            snippet = cleaned[start : m.end() + 60].replace("\n", " ")
        findings.append(
            Finding(
                code="PROMPT_INJECTION",
                severity=Severity.CRITICAL,
                message="Document contains instructions addressed to the AI agent. Documents are data, never commands.",
                evidence={"patterns": len(hits), "snippet": snippet.strip()},
            )
        )
    if BASE64_BLOB_RE.search(cleaned):
        findings.append(
            Finding(
                code="ENCODED_PAYLOAD",
                severity=Severity.MEDIUM,
                message="Document contains a long encoded blob that could carry hidden instructions.",
            )
        )
    pressure = [p for p in PRESSURE_PATTERNS if re.search(p, lower)]
    if pressure:
        findings.append(
            Finding(
                code="SOCIAL_ENGINEERING_PRESSURE",
                severity=Severity.MEDIUM,
                message="Urgency or changed-payment-details language, a hallmark of business email compromise (BEC).",
                evidence={"signals": len(pressure)},
            )
        )
    return findings


def is_lookalike(candidate: str, known: str, prefix: int = 4, suffix: int = 4) -> bool:
    """Address poisoning: different address that shares the visible prefix/suffix of a known one."""
    c, k = candidate.lower(), known.lower()
    if c == k:
        return False
    return c[2 : 2 + prefix] == k[2 : 2 + prefix] and c[-suffix:] == k[-suffix:]


def addresses_in(text: str) -> list[str]:
    return sorted({a.lower() for a in ADDRESS_RE.findall(text)})


def normalize_name(name: str) -> str:
    folded, _ = fold_confusables(name)
    s = folded.casefold()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    stop = {"pt", "cv", "co", "ltd", "pte", "inc", "llc", "tbk", "the", "limited", "company", "persero"}
    return " ".join(w for w in s.split() if w not in stop)
