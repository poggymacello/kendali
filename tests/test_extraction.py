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


# --- tolerant layouts (red-team P03 / P07 / fresh probe N4)
from kendali.invoices import extract_deterministic, parse_date_ex  # noqa: E402

LCL = "0x7b7EE44a2A7d49B8dfA509EDd19f9a516FE73D1e"


def test_unlabeled_header_layout_p07():
    inv = extract_deterministic(
        "Lion City Logistics Pte. Ltd. - TAX INVOICE\nUEN: UEN-201912345K\nInvoice #: LCL-77901\nDate: 10/10/2026\n"
        "Payment due: 13/10/2026\nSea freight SIN, 1 x 300.00 = 300.00\nAmount payable: 300.00 tUSDC\n"
        f"Wallet: {LCL}\n", "p07.txt")
    assert inv.vendor_name == "Lion City Logistics Pte. Ltd."
    assert inv.registration_no == "UEN-201912345K"
    assert inv.invoice_no == "LCL-77901"
    assert inv.issue_date == date(2026, 10, 10) and inv.due_date == date(2026, 10, 13)
    assert inv.total == Decimal("300.00") and inv.currency == "TUSDC"  # inferred from the total line
    assert inv.pay_to == LCL.lower()
    assert len(inv.line_items) == 1 and arithmetic_ok(inv)[0]
    assert all(not w.startswith("unreadable") for w in inv.warnings)


def test_indonesian_labels_p03():
    inv = extract_deterministic(
        "INVOICE\nDari: CV Bandung Roastery Equipment\nNo. Registrasi: NIB-8120005566778\nNo. Invoice: BRE-2026-099\n"
        "Tanggal: 2026-10-10\nJatuh Tempo: 2026-10-13\nMata Uang: tUSDC\nRincian:\n- Heating element | 1 x 640.00 = 640.00\n"
        "Total: 640.00 tUSDC\nBayar ke (wallet): 0x3A82fBD378e7101BE48643a7c3A839FAa4AEb5dD\n", "p03.txt")
    assert (inv.vendor_name, inv.registration_no, inv.invoice_no) == (
        "CV Bandung Roastery Equipment", "NIB-8120005566778", "BRE-2026-099")
    assert inv.total == Decimal("640.00") and inv.pay_to.startswith("0x3a82")


def test_thousands_separator_and_idr_total():
    inv = extract_deterministic("Dari: X\nNomor Faktur: A-1\n- Beans | 125 x 10.00 = 1,250.00\nJumlah Tagihan: 1,250.00 tUSDC\n", "a")
    assert inv.total == Decimal("1250.00") and arithmetic_ok(inv)[0]
    idr = extract_deterministic("Dari: X\nNo. Invoice: B-1\nMata Uang: IDR\nTotal: Rp 640.000\n", "b")
    assert idr.currency == "IDR" and idr.total_currency == "IDR"


def test_stronger_total_label_wins_over_bare_jumlah():
    inv = extract_deterministic("Dari: X\nNomor Faktur: A-2\nJumlah: 3\nJumlah Tagihan: 990.00 tUSDC\n", "c")
    assert inv.total == Decimal("990.00")


def test_dates_are_day_first_and_never_guessed_month_first():
    assert parse_date_ex("13/10/2026") == (date(2026, 10, 13), None)
    d, note = parse_date_ex("10/11/2026")
    assert d == date(2026, 11, 10) and note.startswith("assumed")  # ambiguity is recorded
    d, note = parse_date_ex("10/13/2026")  # US month-first: refuse to guess
    assert d is None and note.startswith("unreadable")
    assert parse_date_ex("13 Oktober 2026")[0] == date(2026, 10, 13)
    assert parse_date_ex("2026-10-13")[0] == date(2026, 10, 13)


def test_po_reference_is_extracted():
    inv = extract_deterministic("From: X\nInvoice No: Q-1\nPO No: po-2026-0421\nTotal Due: 10.00 tUSDC\n", "d")
    assert inv.po_ref == "PO-2026-0421"


def test_beneficiary_name_line_is_not_a_wallet():
    inv = extract_deterministic(f"From: X\nInvoice No: Q-2\nBeneficiary: Lion City Logistics\nWallet: {LCL}\n", "e")
    assert inv.pay_to == LCL.lower()


def test_pdf_bullet_line_item(inbox):
    inv = load_invoice(inbox / "inv-13-bandung-BRE-2026-031.pdf")
    assert len(inv.line_items) == 1 and arithmetic_ok(inv)[0]
