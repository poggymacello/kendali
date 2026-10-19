"""Deterministic security detectors. None of these rely on the LLM.

* prompt-injection / instruction smuggling inside untrusted documents
* hidden characters (zero-width, bidi overrides) and homoglyph impersonation
* claims of prior approval / text addressed to an automated reader ("pre-cleared by the owner")
* social-engineering pressure (changed payment details, threats, urgency attached to a payment demand)
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

# Claims of prior approval, or text addressed to an automated reader. A document can never carry an
# approval (approvals are owner signatures on-chain), so these route to a human. This is defence-in-depth:
# patterns can be paraphrased, and fund safety does not depend on them (see SECURITY_SELF_ASSESSMENT.md).
APPROVAL_CLAIM_PATTERNS = [
    # addressed to an automated reader ("For the automated accounts-payable tool reading this")
    r"\b(to|for|attention|attn|dear|hello|hi|note\s+to)\s*:?\s+(the\s+|any\s+|an?\s+|our\s+|your\s+)?"
    r"(automated|automatic|auto|ai)\b[\w\s/-]{0,40}\b(tool|system|agent|bot|assistant|processor|software|pipeline|workflow|reader)",
    r"\b(tool|system|agent|bot|software|ai|model|program|assistant)\s+(that\s+is\s+)?(reading|processing|parsing|handling|reviewing)\s+this\b",
    r"\b(if|when)\s+you\s+are\s+(an?\s+)?(automated|ai|bot|machine|program|language\s+model)",
    # claims that approval already happened or is not needed
    r"\b(pre|already)[\s-]?(cleared|approved|authori[sz]ed|signed[\s-]?off|okayed)\b",
    r"\b(approved|cleared|authori[sz]ed|okayed|signed\s+off|confirmed)\s+(already\s+)?(by|with)\s+(the\s+|your\s+)?"
    r"(owner|ceo|director|boss|management|treasurer|finance|cfo|founder)",
    r"\bno\s+(further\s+|additional\s+|extra\s+|other\s+)?(sign[\s-]?off|approval|review|check|verification|confirmation|call[\s-]?back)s?"
    r"\s+(is\s+|are\s+)?(needed|required|necessary)",
    r"\b(no\s+need|not\s+necessary|unnecessary|don'?t\s+need)\s+to\s+(check|verify|review|approve|confirm|call|wait)",
    # Bahasa Indonesia (formal + chat slang)
    r"\b(sudah|udah|dah|telah)\s+(di\s*)?(acc|disetujui|approve|diapprove|approved|diotorisasi)\b",
    r"\b(oke|ok|okay|acc|disetujui|setuju|approve)\s+(dari|oleh|sama|ama)\s+(bos|boss|owner|pemilik|atasan|direktur|pak|bu|"
    r"bapak|ibu)\b",
    r"\b(gausah|ga\s*usah|gak\s*usah|nggak\s*usah|ngga\s*usah|enggak\s*usah|ndak\s*usah|tidak\s+usah|tidak\s+perlu|tak\s+perlu|"
    r"ga\s*perlu|gak\s*perlu|nggak\s*perlu)\b.{0,30}\b(cek|dicek|ngecek|periksa|diperiksa|nunggu|menunggu|tunggu|approval|"
    r"persetujuan|konfirmasi|dikonfirmasi|verifikasi|diverifikasi|telepon|telpon|ditelpon|izin)",
    r"\bproses\s+(aja|saja|langsung)\b",
    r"\b(buat|kepada|halo|hai|yth\.?)\s+(sistem|bot|robot|ai|mesin)(nya)?\b",
]

# Social-engineering pressure. Urgency words alone ("urgent air freight", "urgent shipment") describe
# goods and are NOT flagged; only (a) changed payment details, (b) threats / deadlines, or (c) urgency
# attached to a demand to pay are.
PAYMENT_CHANGE_PATTERNS = [
    r"\b(changed|updated|new|moved|switched|migrated)\s+(our\s+|the\s+)?(bank|banking|payment|wallet|account|remittance|"
    r"beneficiary|receiving)\s+(details|information|info|address|arrangements?|account|number|wallet)\b",
    r"\b(changed|updated|moved|switched|migrated)\s+(our\s+|the\s+)?(wallet|bank)\b",
    r"\bnew\s+(wallet|bank\s+account|beneficiary|receiving\s+address)\b",
    r"\b(bank|payment|wallet|remittance)\s+(details|information|address|arrangements?)\s+(have|has|were|was)\s+(been\s+)?"
    r"(changed|updated|moved)",
    r"\b(do\s+not|don'?t)\s+(use|pay)\s+(the\s+|our\s+)?(old|previous)\s+(address|wallet|account)",
    r"\b(rekening|wallet|alamat\s+wallet|nomor\s+rekening)\s+(baru|kami\s+berubah|berubah|sudah\s+ganti)",
    r"\bganti\s+(rekening|wallet)\b",
]
THREAT_PATTERNS = [
    r"\b(account|service|supply|delivery|shipment|subscription)\s+will\s+be\s+(suspended|terminated|closed|stopped|"
    r"cancell?ed|held|blocked)",
    r"\b(late|overdue)\s+(fee|penalty|charge|interest)",
    r"\blegal\s+action\b",
    r"\bwithin\s+\d+\s+(hour|hours|minutes|jam|menit)\b",
    r"\bhari\s+ini\s+juga\b",
    r"\bsekarang\s+juga\b",
    r"\bdenda\b",
    r"\b(akan\s+)?(diblokir|diputus|dihentikan)\b",
]
_URGENCY = r"(urgent(ly)?|immediately|asap|right\s+away|without\s+delay|as\s+soon\s+as\s+possible|segera|secepatnya)"
_PAY = r"(pay|paid|payment|transfer|remit|remittance|settle|settlement|wire|send|bayar|dibayar|bayarkan|lunasi|pelunasan|" \
       r"pembayaran|kirim|transfernya)"
URGENT_DEMAND_PATTERNS = [
    rf"\b{_URGENCY}\b\W+(?:\w+\W+){{0,4}}?{_PAY}\b",
    rf"\b{_PAY}\b\W+(?:\w+\W+){{0,4}}?{_URGENCY}\b",
    r"\bimmediate\s+(payment|transfer|settlement)\b",
]
PRESSURE_PATTERNS = PAYMENT_CHANGE_PATTERNS + THREAT_PATTERNS + URGENT_DEMAND_PATTERNS

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
    claims = [p for p in APPROVAL_CLAIM_PATTERNS if re.search(p, lower)]
    if claims and not hits:
        m = re.search(claims[0], lower)
        snippet = cleaned[max(0, m.start() - 40) : m.end() + 60].replace("\n", " ").strip() if m else ""
        findings.append(
            Finding(
                code="UNVERIFIED_APPROVAL_CLAIM",
                severity=Severity.HIGH,
                message=("Document claims prior approval or addresses an automated reader. Documents cannot approve "
                         "payments; only the owner's on-chain signature can, so a human must review."),
                evidence={"patterns": len(claims), "snippet": snippet},
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
