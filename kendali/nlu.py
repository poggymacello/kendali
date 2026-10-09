"""Offline, deterministic intent parser (English + Bahasa Indonesia).

Used when no LLM is configured and as the reproducible baseline in evaluation. Mandate
violations are detected FIRST so no phrasing can turn a forbidden request into an action.
"""

from __future__ import annotations

import re

from .models import Intent

ID_HINTS = (
    r"\b(bayar|tagihan|semua|tolong|berapa|saldo|kas|kenapa|hentikan|jeda|setujui|naikkan|kirim|ke|yang|minggu|ini|"
    r"sisa|cadangan|parkir|rutin|riwayat|menunggu|batas|harian|jadi|ya|sekarang|dong|mau|tidak|untuk|dari|dan|kita|"
    r"sudah|belum|apa|ubah|ganti|tambah|tambahkan|daftarkan|lanjutkan|izin)\b"
)

FORBIDDEN = [
    (r"\b(approve|setujui|acc)\b.{0,40}\b(proposal|usulan|pending|#?\d+)", "AGENT_CANNOT_APPROVE"),
    (r"\b(raise|increase|change|set|update|naikkan|ubah|ganti)\b.{0,30}\b(limit|cap|batas|plafon)", "AGENT_CANNOT_CHANGE_POLICY"),
    (r"\b(add|register|whitelist|allowlist|tambah(kan)?|daftarkan)\b.{0,30}\b(payee|vendor|supplier|penerima|wallet)", "AGENT_CANNOT_CHANGE_POLICY"),
    (r"\b(unpause|resume|lanjutkan pembayaran|aktifkan lagi)\b", "AGENT_CANNOT_CHANGE_POLICY"),
    (r"\b(approve|allowance|izin)\b.{0,40}\b(token|unlimited|tak terbatas|spend|spender)", "TOKEN_APPROVAL_NOT_SUPPORTED"),
    (r"\b(send|transfer|pay|kirim|bayar)\b.{0,60}0x[0-9a-fA-F]{6,}", "RAW_ADDRESS_NOT_ALLOWED"),
    (r"\b(i am|this is|saya)\b.{0,20}\b(the )?(owner|pemilik|ceo|director|direktur)\b", "IDENTITY_CLAIM_NOT_ACCEPTED"),
]

INTENTS = [
    (r"\b(pause|stop all payments|freeze|emergency stop|hentikan|jeda|bekukan)\b", "PAUSE"),
    (r"\b(pending|waiting for approval|approvals?|menunggu persetujuan|perlu persetujuan)\b", "LIST_PENDING"),
    (r"\b(what|why|which|apa|kenapa|mengapa|riwayat|history)\b.{0,60}\b(paid|pay|bayar|dibayar|pembayaran|payment)", "AUDIT_QUERY"),
    (r"\b(runway|idle cash|park|sweep|rebalance|reserve|cadangan|parkir|sisa kas|simpan)\b", "REBALANCE_TREASURY"),
    (r"\b(recurring|scheduled|subscription|rent|sewa|rutin|langganan|terjadwal)\b", "RUN_OBLIGATIONS"),
    (r"\b(pay|bayar)\b.{0,20}\b(invoice|faktur|tagihan)\s+((?=[\w\-/]*\d)[A-Za-z0-9][A-Za-z0-9\-/]{3,})", "PAY_INVOICE"),
    (r"\b(pay|process|bayar|proses)\b.{0,40}\b(invoices?|bills?|inbox|tagihan|faktur)\b", "PROCESS_INBOX"),
    (r"\b(how much|balance|cash position|treasury|saldo|kas|berapa|posisi)\b", "CASH_REPORT"),
    (r"\b(help|bantuan|what can you do|bisa apa)\b", "HELP"),
]


def detect_language(text: str) -> str:
    return "id" if len(re.findall(ID_HINTS, text.lower())) >= 2 else "en"


def parse(message: str) -> Intent:
    text = message.strip()
    lower = text.lower()
    lang = detect_language(text)
    for pat, reason in FORBIDDEN:
        if re.search(pat, lower if "0x" not in pat else text, re.IGNORECASE):
            return Intent(name="REFUSE", params={"reason": reason}, language=lang)
    for pat, name in INTENTS:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        params: dict = {}
        if name == "PAY_INVOICE":
            params["invoice_no"] = m.group(3).upper()
        if name == "AUDIT_QUERY":
            v = re.search(r"\b(to|ke|kepada|for|untuk)\s+([A-Za-z][\w .&-]{2,40})", text)
            params["vendor"] = v.group(2).strip(" ?.") if v else None
        if name == "REBALANCE_TREASURY":
            d = re.search(r"(\d+)\s*(day|days|hari)", lower)
            w = re.search(r"(\d+)\s*(week|weeks|minggu)", lower)
            params["runway_days"] = int(d.group(1)) if d else (int(w.group(1)) * 7 if w else None)
        if name == "PROCESS_INBOX":
            if re.search(r"this week|minggu ini", lower):
                params["due_within_days"] = 7
            elif re.search(r"today|hari ini", lower):
                params["due_within_days"] = 0
        return Intent(name=name, params=params, language=lang)
    return Intent(name="HELP", params={"unrecognised": True}, language=lang)
