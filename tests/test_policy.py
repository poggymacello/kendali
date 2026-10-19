"""Policy routing without a chain: the decision table is unit-testable on its own."""

from decimal import Decimal

from kendali.invoices import load_invoice
from kendali.models import Action
from kendali.money import to_units
from kendali.policy import PolicyEngine, VaultView

NOW = 1791770400  # 2026-10-12 02:00 UTC


def view(**kw):
    base = dict(now=NOW, paused=False, auto_limit=to_units(1000), daily_remaining=to_units(2500),
                hard_cap=to_units(10000), liquid=to_units(25000), reserve=0)
    base.update(kw)
    return VaultView(**base)


ACTIVE = {"allowed": True, "activeFrom": 0}


def decide(registry, inbox, name, v=None, payee=ACTIVE, ref_used=False, ledger=None, **kw):
    inv = load_invoice(inbox / name)
    return PolicyEngine(registry).evaluate_invoice(inv, v or view(), payee, ref_used, ledger, **kw)


def test_legit_executes(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt")
    assert d.action == Action.EXECUTE and d.amount == Decimal("540.00")
    assert d.payee == registry.vendors["V002"].wallet


def test_above_solo_limit_needs_approval(registry, inbox):
    assert decide(registry, inbox, "inv-02-gayo-KTG-0915.txt").action == Action.REQUEST_APPROVAL


def test_bec_blocked(registry, inbox):
    d = decide(registry, inbox, "inv-04-huaxin-HX-2026-1077-BEC.txt")
    assert d.action == Action.BLOCK and "PAYMENT_DETAILS_CHANGED" in d.codes()


def test_not_due_held(registry, inbox):
    assert decide(registry, inbox, "inv-03-lioncity-LCL-77812.txt").action == Action.HOLD


def test_force_pays_early(registry, inbox):
    assert decide(registry, inbox, "inv-03-lioncity-LCL-77812.txt", force=True).action == Action.EXECUTE


def test_duplicate_blocked(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", ref_used=True)
    assert d.action == Action.BLOCK and "DUPLICATE_INVOICE" in d.codes()


def test_paused_holds(registry, inbox):
    assert decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", v=view(paused=True)).action == Action.HOLD


def test_insufficient_funds_holds(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", v=view(liquid=to_units(100)))
    assert d.action == Action.HOLD and "INSUFFICIENT_FUNDS" in d.codes()


def test_reserve_withdrawal_planned(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", v=view(liquid=to_units(100), reserve=to_units(5000)))
    assert d.action == Action.EXECUTE and "RESERVE_WITHDRAWAL" in d.codes() and d.plan


def test_daily_budget_routes_to_approval(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", v=view(daily_remaining=to_units(100)))
    assert d.action == Action.REQUEST_APPROVAL and "DAILY_LIMIT_REACHED" in d.codes()


def test_payee_not_onchain_blocked(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", payee={"allowed": False, "activeFrom": 0})
    assert d.action == Action.BLOCK


def test_llm_disagreement_needs_human(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", llm_diffs=["total"])
    assert d.action == Action.REQUEST_APPROVAL and "EXTRACTION_MISMATCH" in d.codes()


def test_llm_flag_alone_blocks(registry, inbox):
    d = decide(registry, inbox, "inv-01-huaxin-HX-2026-1042.txt", llm_flagged_instructions=True)
    assert d.action == Action.BLOCK


# --- purchase-order matching, currency and extraction safety (red-team round 19 Oct 2026)
from kendali.invoices import extract_deterministic  # noqa: E402

V002 = "0xD287872aBBEB5876A2F784d79eA155c5e03a843e"


def huaxin(no, amount, extra=""):
    return extract_deterministic(
        f"INVOICE\nFrom: Shenzhen Huaxin Packaging Co., Ltd.\nRegistration No: USCC-91440300MA5G7K2X1Q\nInvoice No: {no}\n"
        f"{extra}Issue Date: 2026-10-10\nDue Date: 2026-10-13\nCurrency: tUSDC\nTotal Due: {amount} tUSDC\n"
        f"Pay to (wallet): {V002}\n", f"{no}.txt")


def run(registry, inv, **kw):
    return PolicyEngine(registry).evaluate_invoice(inv, view(), ACTIVE, False, None, **kw)


def test_invoice_without_po_needs_human(registry):
    d = run(registry, huaxin("HX-T-1", "780.00"))
    assert d.action == Action.REQUEST_APPROVAL and "NO_MATCHING_PO" in d.codes() and d.po_id is None


def test_po_tolerance_boundary(registry):
    ok = run(registry, huaxin("HX-T-2", "856.80", "PO No: PO-2026-0421\n"))
    assert ok.action == Action.EXECUTE and ok.po_id == "PO-2026-0421"
    over = run(registry, huaxin("HX-T-3", "857.00", "PO No: PO-2026-0421\n"))
    assert over.action == Action.REQUEST_APPROVAL and "PO_AMOUNT_MISMATCH" in over.codes()


def test_forged_po_reference(registry):
    unknown = run(registry, huaxin("HX-T-4", "600.00", "PO No: PO-2026-0499\n"))
    other_vendor = run(registry, huaxin("HX-T-5", "300.00", "PO No: PO-2026-0433\n"))
    for d in (unknown, other_vendor):
        assert d.action == Action.REQUEST_APPROVAL and "PO_REFERENCE_INVALID" in d.codes()


def test_po_is_consumed(registry):
    usage = {"PO-2026-0412": ["0xsome-other-ref"]}
    d = run(registry, huaxin("HX-T-6", "540.00"), po_usage=usage)
    assert d.action == Action.REQUEST_APPROVAL and "NO_MATCHING_PO" in d.codes()
    blanket = {"PO-2026-0425": ["0xa", "0xb"]}  # 3 call-offs, 2 used
    assert run(registry, huaxin("HX-T-7", "950.00"), po_usage=blanket).po_id == "PO-2026-0425"


def test_foreign_currency_is_blocked(registry):
    inv = huaxin("HX-T-8", "540.00")
    inv.currency = "IDR"
    assert run(registry, inv).action == Action.BLOCK
    inv.currency, inv.total_currency = "TUSDC", "SGD"  # contradicting currency lines
    assert run(registry, inv).action == Action.BLOCK


def test_unstated_currency_needs_human(registry):
    inv = huaxin("HX-T-9", "540.00")
    inv.currency = inv.total_currency = None
    d = run(registry, inv)
    assert d.action == Action.REQUEST_APPROVAL and "CURRENCY_UNSTATED" in d.codes()


def test_unreadable_date_needs_human(registry):
    inv = huaxin("HX-T-10", "540.00")
    inv.warnings.append("unreadable: date '10/13/2026' (expected day/month/year)")
    assert run(registry, inv).action == Action.REQUEST_APPROVAL


def test_vendor_identified_by_registration_only_needs_human(registry):
    inv = huaxin("HX-T-11", "540.00")
    inv.vendor_name = None
    d = run(registry, inv)
    assert d.action == Action.REQUEST_APPROVAL and "VENDOR_NAME_UNREAD" in d.codes()
