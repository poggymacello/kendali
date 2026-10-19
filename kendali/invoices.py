"""Invoice ingestion and deterministic field extraction (the LLM-independent baseline).

The extractor is deliberately tolerant about *layout* (label synonyms in English and Bahasa
Indonesia, unlabeled vendor header line, day-first dates, currency on the total line) and
deliberately strict about *meaning*: anything it cannot read unambiguously is reported in
``Invoice.warnings`` so the policy routes the invoice to a human instead of guessing.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .models import Invoice, LineItem
from .money import parse_amount
from .security import ADDRESS_RE, strip_hidden

# Label synonyms per field (EN + ID). Matched at the start of a line, case-insensitive.
LABELS: dict[str, list[str]] = {
    "vendor_name": [
        r"from", r"bill(?:ed)?\s*from", r"billed\s*by", r"vendor", r"supplier", r"seller", r"issuer", r"issued\s*by",
        r"dari", r"penjual", r"pemasok", r"penerbit",
    ],
    "registration_no": [
        r"(?:company\s*|business\s*)?registration(?:\s*no\.?|\s*number)?", r"reg\.?\s*no\.?", r"company\s*no\.?",
        r"uen", r"nib", r"npwp", r"uscc", r"unified\s*social\s*credit\s*code",
        r"no\.?\s*registrasi", r"nomor\s*registrasi", r"nomor\s*induk\s*berusaha",
    ],
    "invoice_no": [
        r"(?:tax\s*)?invoice\s*(?:no\.?|number|nr\.?|#)", r"inv\.?\s*(?:no\.?|#)", r"invoice",
        r"no\.?\s*(?:invoice|faktur)", r"nomor\s*(?:invoice|faktur)", r"faktur\s*no\.?", r"bill\s*no\.?",
    ],
    "issue_date": [
        r"issue\s*date", r"invoice\s*date", r"date\s*of\s*issue", r"issued(?:\s*on)?", r"date",
        r"tanggal(?:\s*(?:faktur|invoice))?", r"tgl\.?(?:\s*faktur)?",
    ],
    "due_date": [
        r"due\s*date", r"payment\s*due(?:\s*date)?", r"due(?:\s*(?:by|on))?", r"pay\s*by",
        r"(?:tanggal\s*|tgl\.?\s*)?jatuh\s*tempo", r"batas\s*pembayaran",
    ],
    "currency": [r"currency", r"mata\s*uang", r"valuta"],
    "total": [
        r"total\s*due", r"amount\s*due", r"amount\s*payable", r"total\s*payable", r"balance\s*due", r"grand\s*total",
        r"invoice\s*total", r"total\s*amount", r"total", r"jumlah\s*tagihan", r"total\s*tagihan", r"jumlah\s*dibayar",
        r"total\s*bayar", r"yang\s*harus\s*dibayar", r"jumlah",
    ],
    "pay_to": [
        r"pay\s*to", r"payment\s*(?:address|wallet)", r"beneficiary(?:\s*wallet)?", r"wallet(?:\s*address)?",
        r"remit\s*to", r"send\s*to", r"alamat\s*wallet(?:\s*pembayaran)?", r"transfer\s*ke", r"bayar\s*ke",
        r"kirim\s*ke", r"rekening\s*tujuan",
    ],
    "po_ref": [
        r"p\.?o\.?\s*(?:no\.?|number|#|ref\.?)?", r"purchase\s*order(?:\s*(?:no\.?|number|#))?",
        r"(?:no\.?|nomor)\s*p\.?o\.?", r"your\s*order(?:\s*(?:no\.?|ref\.?))?",
    ],
}
# a colon, or a dash surrounded by spaces, optionally after a parenthesised hint such as "(wallet)"
SEP = r"\s*(?:\([^)]*\))?\s*(?::|\s[-–]\s)\s*"
# key -> one regex per label, in priority order (a stronger label later in the document beats a weaker one)
FIELD_RES = {
    key: [re.compile(r"^(?:" + alt + r")" + (r"[^:\n]{0,30}?" if key == "pay_to" else "") + SEP + r"(.+)$",
                     re.IGNORECASE) for alt in alts]
    for key, alts in LABELS.items()
}
INVOICE_HASH_RE = re.compile(r"^(?:tax\s*)?invoice\s*#\s*:?\s*([A-Za-z0-9][\w\-/]+)", re.IGNORECASE)
NUM = r"\d[\d.,]*"
LINE_ITEM_RE = re.compile(
    rf"^(?:[^\w\s(]\s*)?(.+?)\s*[|,;:]\s*({NUM})\s*[x×*]\s*({NUM})\s*=\s*({NUM})", re.IGNORECASE)
NOTES_RE = re.compile(r"^(?:notes?|catatan|remarks|keterangan)\s*[:\-]\s*(.*)$", re.IGNORECASE)
AMOUNT_RE = re.compile(r"^(?P<pre>[A-Za-z$€£¥]{1,6}\.?)?\s*(?P<num>\d[\d.,]*)\s*(?P<post>[A-Za-z$]{1,6})?\b")
HEADER_WORDS_RE = re.compile(r"\b(?:tax\s+invoice|invoice|faktur(?:\s+pajak)?|bill|receipt|tagihan|kwitansi)\b",
                             re.IGNORECASE)

# Currency tokens we recognise. Anything else is passed through verbatim and fails the policy's currency check.
CURRENCY_TOKENS = {
    "TUSDC": "TUSDC", "USDC": "USDC", "USD": "USD", "US$": "USD",
    "RP": "IDR", "RP.": "IDR", "IDR": "IDR", "SGD": "SGD", "S$": "SGD", "CNY": "CNY", "RMB": "CNY", "¥": "CNY",
}

MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12, "agu": 8, "agt": 8, "okt": 10, "des": 12,
}


def parse_date_ex(s: str | None) -> tuple[date | None, str | None]:
    """Parse a date. Returns (date, note). Numeric dates are read DAY-FIRST (Indonesia/Singapore convention).

    * ``2026-10-13`` / ``2026/10/13``: ISO, unambiguous.
    * ``13/10/2026``: day-first. ``10/11/2026`` is read as 10 November and a note records the assumption.
    * ``10/13/2026`` (month-first) is NOT guessed: it returns (None, "unreadable: ...") so a human checks it.
    """
    if not s:
        return None, None
    s = s.strip().rstrip(".")
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
        except ValueError:
            return None, f"unreadable: date {s!r}"
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = date(y, b, a)
        except ValueError:
            return None, f"unreadable: date {s!r} (expected day/month/year)"
        note = f"assumed: date {s!r} read day-first as {d.isoformat()}" if a <= 12 and b <= 12 and a != b else None
        return d, note
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%d %B, %Y"):
        try:
            return datetime.strptime(s, fmt).date(), None
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})$", s)
    if m and m.group(2).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))), None
        except ValueError:
            pass
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        return datetime.strptime(m.group(0), "%Y-%m-%d").date(), None
    return None, f"unreadable: date {s!r}"


def parse_date(s: str | None) -> date | None:
    return parse_date_ex(s)[0]


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8")


def _currency_token(tok: str | None) -> str | None:
    if not tok:
        return None
    t = tok.strip().upper()
    return CURRENCY_TOKENS.get(t, t)


def parse_total(value: str) -> tuple[Decimal | None, str | None]:
    """'540.00 tUSDC' -> (540.00, 'TUSDC'); 'Rp 640.000' -> (640.000, 'IDR'); '1,250.00' -> (1250.00, None)."""
    m = AMOUNT_RE.match(value.strip())
    if not m:
        return None, None
    cur = _currency_token(m.group("pre")) or _currency_token(m.group("post"))
    return parse_amount(m.group("num").rstrip(".,")), cur


def header_vendor(lines: list[str]) -> str | None:
    """Vendor name from an unlabeled first line such as 'Lion City Logistics Pte. Ltd. - TAX INVOICE'."""
    first = next((ln.strip() for ln in lines if ln.strip()), "")
    if not first or ":" in first or ADDRESS_RE.search(first):
        return None
    name = HEADER_WORDS_RE.sub(" ", first)
    name = re.sub(r"\s*[-–—|/]+\s*$", "", re.sub(r"^\s*[-–—|/]+\s*", "", name)).strip()
    name = re.sub(r"\s{2,}", " ", name).strip(" -|/")
    return name if len(re.sub(r"[^A-Za-z]", "", name)) >= 3 else None


def extract_deterministic(raw_text: str, source: str) -> Invoice:
    text, _ = strip_hidden(raw_text)
    fields: dict[str, str] = {}
    notes: list[str] = []
    items: list[LineItem] = []
    warnings: list[str] = []
    in_notes = False
    lines = text.splitlines()
    prio: dict[str, int] = {}
    for line in lines:
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
        mh = INVOICE_HASH_RE.match(s)
        if mh:
            matched = True
            if prio.get("invoice_no", 99) > 0:
                fields["invoice_no"], prio["invoice_no"] = mh.group(1), 0
        for key, rxs in FIELD_RES.items():
            if matched:
                break
            for idx, rx in enumerate(rxs):
                m = rx.match(s)
                if not m:
                    continue
                value = m.group(1).strip()
                if key == "pay_to" and not ADDRESS_RE.search(value):
                    break  # e.g. "Beneficiary: Lion City Logistics" is not an address line
                matched = True
                if idx < prio.get(key, 99):
                    fields[key], prio[key] = value, idx
                break
        if in_notes and not matched:
            notes.append(s)

    vendor_name = fields.get("vendor_name")
    if not vendor_name:
        vendor_name = header_vendor(lines)
        if vendor_name:
            warnings.append(f"assumed: vendor name read from the unlabeled header line ({vendor_name!r})")

    invoice_no = None
    if fields.get("invoice_no"):
        invoice_no = fields["invoice_no"].split()[0].strip(".,;")

    total, total_cur = (None, None)
    if "total" in fields:
        total, total_cur = parse_total(fields["total"])
        if total is None:
            warnings.append(f"unreadable: total {fields['total']!r}")

    currency = None
    if fields.get("currency"):
        currency = _currency_token(fields["currency"].split()[0])
    elif total_cur:
        currency = total_cur  # e.g. "Amount payable: 300.00 tUSDC" with no Currency line

    pay_to = None
    if fields.get("pay_to"):
        pay_to = ADDRESS_RE.search(fields["pay_to"]).group(0).lower()

    issue, n1 = parse_date_ex(fields.get("issue_date"))
    due, n2 = parse_date_ex(fields.get("due_date"))
    warnings += [n for n in (n1, n2) if n]

    reg = fields.get("registration_no")
    po_ref = fields.get("po_ref")
    return Invoice(
        source=source,
        vendor_name=vendor_name,
        registration_no=reg.split()[0] if reg else None,
        invoice_no=invoice_no,
        issue_date=issue,
        due_date=due,
        currency=currency,
        total=total,
        total_currency=total_cur,
        pay_to=pay_to,
        po_ref=po_ref.split()[0].strip(".,;").upper() if po_ref else None,
        notes="\n".join(notes),
        line_items=items,
        raw_text=raw_text,
        extractor="deterministic",
        warnings=warnings,
    )


def load_invoice(path: Path) -> Invoice:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = json.dumps(data, ensure_ascii=False)
        inv = Invoice(source=path.name, raw_text=raw, extractor="structured", **{k: v for k, v in data.items() if k != "source"})
        if inv.pay_to:
            inv.pay_to = inv.pay_to.lower()
        if inv.currency:
            inv.currency = _currency_token(inv.currency)
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
