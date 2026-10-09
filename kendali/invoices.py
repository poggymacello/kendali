"""Invoice ingestion and deterministic field extraction (the LLM-independent baseline)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .models import Invoice, LineItem
from .money import parse_amount
from .security import ADDRESS_RE, strip_hidden

FIELD_PATTERNS = {
    "vendor_name": r"^(?:from|bill\s*from|vendor|supplier|issuer|dari|penjual)\s*[:\-]\s*(.+)$",
    "registration_no": r"^(?:registration(?:\s*no\.?|\s*number)?|reg\.?\s*no\.?|nib|npwp|uscc|uen|company\s*no\.?)\s*[:\-]\s*(.+)$",
    "invoice_no": r"^(?:invoice\s*(?:no\.?|number|#)|no\.?\s*faktur|nomor\s*(?:invoice|faktur))\s*[:\-]\s*(\S+)",
    "issue_date": r"^(?:issue\s*date|invoice\s*date|date|tanggal(?:\s*faktur)?)\s*[:\-]\s*(.+)$",
    "due_date": r"^(?:due\s*date|payment\s*due|jatuh\s*tempo)\s*[:\-]\s*(.+)$",
    "currency": r"^(?:currency|mata\s*uang)\s*[:\-]\s*([A-Za-z]+)",
    "total": r"^(?:total\s*due|amount\s*due|grand\s*total|total|jumlah\s*tagihan|total\s*tagihan)\s*[:\-]\s*([\d.,]+)",
    "pay_to": r"(?:pay\s*to|payment\s*address|beneficiary\s*wallet|wallet\s*address|alamat\s*wallet|transfer\s*ke)[^:\n]*[:\-]\s*(0x[0-9a-fA-F]{40})",
}
LINE_ITEM_RE = re.compile(r"^-\s*(.+?)\s*\|\s*([\d.,]+)\s*x\s*([\d.,]+)\s*=\s*([\d.,]+)", re.IGNORECASE)
NOTES_RE = re.compile(r"^(?:notes?|catatan|remarks|keterangan)\s*[:\-]\s*(.*)$", re.IGNORECASE)


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return datetime.strptime(m.group(0), "%Y-%m-%d").date() if m else None


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8")


def extract_deterministic(raw_text: str, source: str) -> Invoice:
    text, _ = strip_hidden(raw_text)
    fields: dict[str, str] = {}
    notes: list[str] = []
    items: list[LineItem] = []
    in_notes = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            in_notes = False
            continue
        m = NOTES_RE.match(s)
        if m:
            in_notes = True
            if m.group(1):
                notes.append(m.group(1).strip())
            continue
        li = LINE_ITEM_RE.match(s)
        if li:
            items.append(
                LineItem(
                    description=li.group(1).strip(),
                    quantity=parse_amount(li.group(2)),
                    unit_price=parse_amount(li.group(3)),
                    amount=parse_amount(li.group(4)) or Decimal(0),
                )
            )
            continue
        matched = False
        for key, pat in FIELD_PATTERNS.items():
            if key in fields:
                continue
            m = re.search(pat, s, re.IGNORECASE)
            if m:
                fields[key] = m.group(1).strip()
                matched = True
                break
        if in_notes and not matched:
            notes.append(s)
    total = parse_amount(fields["total"]) if "total" in fields else None
    pay_to = fields.get("pay_to")
    return Invoice(
        source=source,
        vendor_name=fields.get("vendor_name"),
        registration_no=fields.get("registration_no"),
        invoice_no=fields.get("invoice_no"),
        issue_date=parse_date(fields.get("issue_date")),
        due_date=parse_date(fields.get("due_date")),
        currency=(fields.get("currency") or "").upper() or None,
        total=total,
        pay_to=pay_to.lower() if pay_to else None,
        notes="\n".join(notes),
        line_items=items,
        raw_text=raw_text,
        extractor="deterministic",
    )


def load_invoice(path: Path) -> Invoice:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = json.dumps(data, ensure_ascii=False)
        inv = Invoice(source=path.name, raw_text=raw, extractor="structured", **{k: v for k, v in data.items() if k != "source"})
        if inv.pay_to:
            inv.pay_to = inv.pay_to.lower()
        return inv
    raw = read_text(path)
    return extract_deterministic(raw, path.name)


def arithmetic_ok(inv: Invoice) -> tuple[bool, str]:
    """Line items must multiply out and add up to the stated total."""
    if not inv.line_items or inv.total is None:
        return True, ""
    for li in inv.line_items:
        if li.quantity is not None and li.unit_price is not None:
            if abs(li.quantity * li.unit_price - li.amount) > Decimal("0.01"):
                return False, f"line '{li.description}': {li.quantity} x {li.unit_price} != {li.amount}"
    s = sum((li.amount for li in inv.line_items), Decimal(0))
    if abs(s - inv.total) > Decimal("0.01"):
        return False, f"line items sum to {s} but total says {inv.total}"
    return True, ""


def all_addresses(inv: Invoice) -> list[str]:
    return sorted({a.lower() for a in ADDRESS_RE.findall(inv.raw_text)})
