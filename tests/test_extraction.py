from datetime import date
from decimal import Decimal

from kendali.invoices import arithmetic_ok, load_invoice
from kendali.money import parse_amount, to_units


def test_english_invoice(inbox):
    inv = load_invoice(inbox / "inv-01-huaxin-HX-2026-1042.txt")
    assert inv.vendor_name == "Shenzhen Huaxin Packaging Co., Ltd."
    assert inv.invoice_no == "HX-2026-1042"
    assert inv.total == Decimal("540.00")
    assert inv.due_date == date(2026, 10, 14)
    assert inv.pay_to and inv.pay_to.startswith("0x")
    assert len(inv.line_items) == 2 and arithmetic_ok(inv)[0]


def test_indonesian_invoice(inbox):
    inv = load_invoice(inbox / "inv-02-gayo-KTG-0915.txt")
    assert inv.vendor_name == "Koperasi Tani Kopi Gayo"
    assert inv.invoice_no == "KTG-0915"
    assert inv.total == Decimal("2850.00")
    assert inv.registration_no == "NIB-1203004567891"


def test_pdf_invoice(inbox):
    inv = load_invoice(inbox / "inv-13-bandung-BRE-2026-031.pdf")
    assert inv.invoice_no == "BRE-2026-031"
    assert inv.total == Decimal("380.00")


def test_arithmetic_mismatch(inbox):
    inv = load_invoice(inbox / "inv-11-gayo-KTG-0920-arithmetic.txt")
    ok, why = arithmetic_ok(inv)
    assert not ok and "1800" in why


def test_amount_parsing():
    assert parse_amount("1,250.50") == Decimal("1250.50")
    assert parse_amount("1.250,50") == Decimal("1250.50")
    assert parse_amount("12000.00") == Decimal("12000.00")
    assert to_units(Decimal("540.00")) == 540_000_000
