"""Treasury management: keep enough cash liquid for upcoming obligations, park the rest."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from .models import Action, Decision, Finding, Severity
from .money import from_units, to_units
from .policy import VaultView
from .registry import Registry

DEFAULT_RUNWAY_DAYS = 14
SAFETY_FACTOR = Decimal("1.2")
MIN_BUFFER = Decimal("2000")
MIN_MOVE = Decimal("250")


def plan_rebalance(registry: Registry, view: VaultView, upcoming_invoices: list[tuple[str, Decimal]],
                   runway_days: int | None = None, is_paid=None) -> Decision:
    days = runway_days or DEFAULT_RUNWAY_DAYS
    occ = [(o, d) for o, d in registry.obligation_due_dates(view.today, days) if not (is_paid and is_paid(o, d))]
    obligations_total = registry.total(occ)
    invoices_total = sum((a for _, a in upcoming_invoices), Decimal(0))
    needed = (obligations_total + invoices_total) * SAFETY_FACTOR
    target = max(MIN_BUFFER, needed).quantize(Decimal("0.01"))
    liquid = from_units(view.liquid)
    reserve = from_units(view.reserve)
    findings = [
        Finding(
            code="RUNWAY_TARGET",
            severity=Severity.INFO,
            message=(
                f"Next {days} days: obligations {obligations_total} + invoices {invoices_total}; "
                f"target liquid = max({MIN_BUFFER}, needs x {SAFETY_FACTOR}) = {target}."
            ),
            evidence={
                "obligations": [{"id": o.id, "date": d.isoformat(), "amount": str(o.amount)} for o, d in occ],
                "invoices": [{"ref": r, "amount": str(a)} for r, a in upcoming_invoices],
            },
        )
    ]
    plan: list[str] = []
    amount = Decimal(0)
    action = Action.INFO
    if view.paused:
        findings.append(Finding(code="VAULT_PAUSED", severity=Severity.INFO, message="Vault paused; no treasury moves."))
        action = Action.HOLD
    elif liquid - target >= MIN_MOVE:
        amount = (liquid - target).quantize(Decimal("0.01"))
        plan.append(f"sweep {amount} to reserve")
        action = Action.EXECUTE
    elif target - liquid >= Decimal("0.01") and reserve > 0:
        amount = min(target - liquid, reserve).quantize(Decimal("0.01"))
        if amount >= Decimal("0.01"):
            plan.append(f"withdraw {amount} from reserve")
            action = Action.EXECUTE
    subject = f"treasury rebalance (runway {days} days)"
    return Decision(kind="treasury", subject=subject, action=action, amount=amount if amount else None,
                    findings=findings, plan=plan, decided_at=view.now)


def units(amount: Decimal) -> int:
    return to_units(amount)


def next_occurrence_label(start, day_of_month: int) -> str:
    d = start
    for _ in range(62):
        if d.day == day_of_month:
            return d.isoformat()
        d += timedelta(days=1)
    return "?"
