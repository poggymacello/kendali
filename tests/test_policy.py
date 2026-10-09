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
