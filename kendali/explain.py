"""Human explanations of decisions (English / Bahasa Indonesia). Deterministic templates so the
explanation that is hashed and anchored on-chain is reproducible."""

from __future__ import annotations

from .models import Action, Decision, Severity
from .money import fmt

NEXT_STEP = {
    "PAYMENT_DETAILS_CHANGED": (
        "Call the vendor on the contact in our records ({callback}) before changing anything. Never use contact details from the invoice itself.",
        "Telepon vendor lewat kontak di data kita ({callback}) sebelum mengubah apa pun. Jangan pakai kontak yang tertera di invoice.",
    ),
    "PROMPT_INJECTION": (
        "Treat the sender as suspicious and review the document manually.",
        "Anggap pengirim mencurigakan dan periksa dokumen secara manual.",
    ),
    "ADDRESS_POISONING": (
        "Never copy addresses from documents or history; pay only through the vendor master.",
        "Jangan menyalin alamat dari dokumen/riwayat; bayar hanya lewat data vendor terverifikasi.",
    ),
    "SANCTIONS_OR_SCAM_HIT": (
        "Do not pay. Escalate under the compliance procedure.",
        "Jangan dibayar. Eskalasi sesuai prosedur kepatuhan.",
    ),
    "UNKNOWN_VENDOR": (
        "The owner must complete KYB onboarding before this issuer can be paid.",
        "Pemilik harus menyelesaikan onboarding KYB sebelum penerbit ini bisa dibayar.",
    ),
    "DUPLICATE_INVOICE": (
        "Already settled or awaiting approval; check the audit trail before re-paying.",
        "Sudah dibayar atau menunggu persetujuan; cek jejak audit sebelum membayar ulang.",
    ),
    "HOMOGLYPH_IMPERSONATION": (
        "Impersonation attempt: notify the real vendor.",
        "Upaya peniruan identitas: beri tahu vendor yang asli.",
    ),
    "MISSING_FIELDS": ("Request a complete invoice from the vendor.", "Minta invoice lengkap dari vendor."),
    "EXCEEDS_HARD_CAP": (
        "Above the absolute cap: the owner must pay directly or split by contract milestones.",
        "Di atas batas mutlak: pemilik bayar langsung atau dipecah sesuai termin kontrak.",
    ),
    "PAYEE_NOT_ONCHAIN": (
        "The owner must add this vendor as a payee in the vault (a cooling-off period applies).",
        "Pemilik harus menambahkan vendor ini sebagai penerima di vault (berlaku masa tunggu).",
    ),
}

VERB = {
    Action.EXECUTE: ("Paid", "Dibayar"),
    Action.REQUEST_APPROVAL: ("Prepared for your approval", "Disiapkan untuk persetujuan Anda"),
    Action.HOLD: ("On hold", "Ditahan"),
    Action.BLOCK: ("Blocked", "Diblokir"),
    Action.REFUSE: ("Refused", "Ditolak"),
    Action.INFO: ("Info", "Info"),
}


def explain_treasury(d: Decision, lang: str = "en") -> str:
    i = 1 if lang == "id" else 0
    target = next((f.message for f in d.findings if f.code == "RUNWAY_TARGET"), "")
    if d.action == Action.EXECUTE and d.plan:
        head = ("Treasury move: " if i == 0 else "Pergerakan kas: ") + d.plan[0]
    elif d.action == Action.HOLD:
        head = "Treasury on hold (vault paused)." if i == 0 else "Pergerakan kas ditahan (vault dijeda)."
    else:
        head = "Treasury already balanced; no move needed." if i == 0 else "Kas sudah seimbang; tidak perlu dipindah."
    return head + "\n" + ("Basis: " if i == 0 else "Dasar: ") + target


def explain(d: Decision, lang: str = "en", callback: str = "") -> str:
    if d.kind == "treasury":
        return explain_treasury(d, lang)
    i = 1 if lang == "id" else 0
    amount = fmt(d.amount) if d.amount is not None else ""
    head = f"{VERB[d.action][i]}: {d.subject}" + (f" — {amount}" if amount else "")
    important = [f for f in d.findings if f.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM)]
    routing = [f for f in d.findings if f.code in {"ABOVE_AUTO_LIMIT", "DAILY_LIMIT_REACHED", "PAYEE_COOLING_DOWN",
                                                    "NOT_DUE", "INSUFFICIENT_FUNDS", "VAULT_PAUSED", "RESERVE_WITHDRAWAL"}]
    lines = [head]
    reasons = important + [f for f in routing if f not in important]
    if reasons:
        lines.append(("Why: " if i == 0 else "Alasan: ") + " ".join(f"[{f.code}] {f.message}" for f in reasons))
    elif d.action == Action.EXECUTE:
        lines.append(
            "All checks passed: verified vendor, KYB-bound wallet, clean screening, within solo limits."
            if i == 0
            else "Semua pemeriksaan lolos: vendor terverifikasi, wallet sesuai KYB, screening bersih, dalam batas mandiri."
        )
    for f in d.findings:
        if f.code in NEXT_STEP and f.severity == Severity.CRITICAL:
            lines.append(("Next step: " if i == 0 else "Langkah berikutnya: ") + NEXT_STEP[f.code][i].format(callback=callback or "on file"))
            break
    if d.plan:
        lines.append(("Plan: " if i == 0 else "Rencana: ") + "; ".join(d.plan))
    return "\n".join(lines)
