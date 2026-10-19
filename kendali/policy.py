"""Deterministic policy engine: the layer that DECIDES.

The routing table is intentionally simple and auditable:

| Condition                                             | Action            |
|-------------------------------------------------------|-------------------|
| any CRITICAL finding                                  | BLOCK             |
| vault paused / not yet due / insufficient total funds | HOLD              |
| any HIGH finding (e.g. no matching purchase order),   | REQUEST_APPROVAL  |
| above auto limit, daily cap reached, payee cooling-off|                   |
| or risk score >= 15                                   |                   |
| otherwise                                             | EXECUTE           |

The on-chain vault re-checks every hard limit independently, so a bug here can make the agent
*less useful* but cannot make it *less safe*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from web3 import Web3

from .invoices import all_addresses, arithmetic_ok
from .models import Action, Decision, Finding, Invoice, PurchaseOrder, Severity, Vendor
from .money import from_units, to_units
from .registry import Registry
from .security import scan_document

SEVERITY_WEIGHT = {Severity.INFO: 0, Severity.LOW: 5, Severity.MEDIUM: 15, Severity.HIGH: 30, Severity.CRITICAL: 100}
ACCEPTED_CURRENCIES = {"TUSDC", "USDC", "USD"}
PAY_AHEAD_DAYS = 3  # pay invoices at most this many days before due date
ANOMALY_FACTOR = Decimal("1.25")
APPROVAL_SCORE = 15


@dataclass
class VaultView:
    """Snapshot of on-chain state used for routing (re-read right before every decision)."""

    now: int
    paused: bool
    auto_limit: int
    daily_remaining: int
    hard_cap: int
    liquid: int
    reserve: int

    @property
    def today(self) -> date:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(self.now, tz=timezone.utc).date()


def payment_ref(vendor_id: str, invoice_no: str) -> str:
    """Deterministic payment reference -> on-chain duplicate protection."""
    return Web3.to_hex(Web3.keccak(text=f"{vendor_id}|{invoice_no.strip().upper()}"))


def risk_score(findings: list[Finding]) -> int:
    return min(100, sum(SEVERITY_WEIGHT[f.severity] for f in findings))


def route(findings: list[Finding]) -> Action:
    codes = {f.code for f in findings}
    if any(f.severity == Severity.CRITICAL for f in findings):
        return Action.BLOCK
    if codes & {"VAULT_PAUSED", "NOT_DUE", "INSUFFICIENT_FUNDS"}:
        return Action.HOLD
    approval_codes = {"ABOVE_AUTO_LIMIT", "DAILY_LIMIT_REACHED", "PAYEE_COOLING_DOWN"}
    if codes & approval_codes or any(f.severity == Severity.HIGH for f in findings):
        return Action.REQUEST_APPROVAL
    if risk_score(findings) >= APPROVAL_SCORE:
        return Action.REQUEST_APPROVAL
    return Action.EXECUTE


class PolicyEngine:
    def __init__(self, registry: Registry):
        self.registry = registry

    def evaluate_invoice(
        self,
        inv: Invoice,
        view: VaultView,
        payee_state: dict | None,
        ref_used_onchain: bool,
        ledger_status: str | None,
        llm_diffs: list[str] | None = None,
        llm_flagged_instructions: bool = False,
        force: bool = False,
        pay_ahead_days: int = PAY_AHEAD_DAYS,
        po_usage: dict[str, list[str]] | None = None,
    ) -> Decision:
        f: list[Finding] = []
        plan: list[str] = []

        # 1. the document itself is untrusted input
        f += scan_document(inv.raw_text)
        if llm_flagged_instructions and not any(x.code == "PROMPT_INJECTION" for x in f):
            f.append(
                Finding(
                    code="PROMPT_INJECTION",
                    severity=Severity.CRITICAL,
                    message="The LLM extractor reported instructions embedded in the document.",
                )
            )

        # 2. completeness and integrity of extracted fields
        missing = [k for k in ("invoice_no", "total") if getattr(inv, k) in (None, "")]
        if not inv.vendor_name and not inv.registration_no:
            missing.insert(0, "vendor_name")
        if missing:
            f.append(
                Finding(
                    code="MISSING_FIELDS",
                    severity=Severity.CRITICAL,
                    message="Required invoice fields could not be read; manual processing required.",
                    evidence={"missing": missing},
                )
            )
        ok, why = arithmetic_ok(inv)
        if not ok:
            f.append(Finding(code="ARITHMETIC_MISMATCH", severity=Severity.HIGH, message=f"Invoice does not add up: {why}."))
        if llm_diffs:
            f.append(
                Finding(
                    code="EXTRACTION_MISMATCH",
                    severity=Severity.HIGH,
                    message="Independent extractors disagree; a human must confirm the figures.",
                    evidence={"fields": llm_diffs},
                )
            )
        for w in inv.warnings:
            if w.startswith("unreadable"):
                f.append(Finding(code="UNREADABLE_FIELD", severity=Severity.HIGH,
                                 message=f"Extractor could not read a field unambiguously ({w}); a human must confirm it."))
            else:
                f.append(Finding(code="EXTRACTION_ASSUMPTION", severity=Severity.INFO, message=f"Extractor {w}."))
        # The vault settles tUSDC only. Paying a figure denominated in another currency would pay the wrong amount,
        # so a foreign-currency or self-contradicting invoice is refused for manual processing (fail closed).
        currencies = {c.upper() for c in (inv.currency, inv.total_currency) if c}
        bad = sorted(c for c in currencies if c not in ACCEPTED_CURRENCIES)
        if bad or len(currencies) > 1:
            f.append(
                Finding(
                    code="CURRENCY_MISMATCH",
                    severity=Severity.CRITICAL,
                    message=f"Invoice currency ({', '.join(sorted(currencies))}) is not the settlement asset (tUSDC) "
                            "or is stated inconsistently.",
                    evidence={"currency_line": inv.currency, "total_line": inv.total_currency},
                )
            )
        elif not currencies:
            f.append(
                Finding(
                    code="CURRENCY_UNSTATED",
                    severity=Severity.HIGH,
                    message="Invoice states no currency; a human must confirm it is billed in tUSDC.",
                )
            )

        # 3. who is asking to be paid?
        vendor, vf = self.registry.resolve(inv.vendor_name, inv.registration_no)
        f += vf

        # 4. screening of every address in the document + the vendor wallet
        addrs = all_addresses(inv)
        if vendor:
            addrs = sorted(set(addrs) | {vendor.wallet.lower()})
        f += self.registry.screen(addrs)

        # 5. payee binding: the agent only ever pays the KYB wallet from the vendor master
        if inv.pay_to:
            poison = self.registry.poisoning(inv.pay_to)
            if poison:
                f += poison
            elif vendor and inv.pay_to.lower() != vendor.wallet.lower():
                f.append(
                    Finding(
                        code="PAYMENT_DETAILS_CHANGED",
                        severity=Severity.CRITICAL,
                        message=(
                            "Invoice asks for payment to a wallet that differs from the verified vendor record "
                            "(classic business-email-compromise pattern). Verify by calling the vendor's known contact."
                        ),
                        evidence={"invoice_wallet": inv.pay_to, "kyb_wallet": vendor.wallet, "callback": vendor.callback_contact},
                    )
                )

        amount = inv.total
        ref = payment_ref(vendor.id, inv.invoice_no) if vendor and inv.invoice_no else None

        # 6. duplicates (local ledger + on-chain reference)
        if ref and (ref_used_onchain or ledger_status in {"EXECUTE", "REQUEST_APPROVAL"}):
            f.append(
                Finding(
                    code="DUPLICATE_INVOICE",
                    severity=Severity.CRITICAL,
                    message="This invoice reference was already paid or proposed.",
                    evidence={"ref": ref, "onchain": ref_used_onchain, "ledger": ledger_status},
                )
            )

        # 7. amount plausibility against the vendor's history
        if vendor and amount is not None and amount > vendor.typical_max * ANOMALY_FACTOR:
            f.append(
                Finding(
                    code="AMOUNT_ANOMALY",
                    severity=Severity.HIGH,
                    message=f"Amount is well above this vendor's usual range ({vendor.typical_min}-{vendor.typical_max}).",
                    evidence={"amount": str(amount)},
                )
            )

        # 8. purchase-order match: was this actually ordered? (three-way-match stand-in)
        po: PurchaseOrder | None = None
        if vendor and amount is not None:
            po, pf = self.match_po(vendor, inv, amount, ref, po_usage or {})
            f += pf

        # 9. timing
        if inv.due_date and not force:
            if inv.due_date > view.today + timedelta(days=pay_ahead_days):
                f.append(
                    Finding(
                        code="NOT_DUE",
                        severity=Severity.INFO,
                        message=f"Due {inv.due_date.isoformat()}; scheduled for payment {pay_ahead_days} days before.",
                    )
                )
            elif inv.due_date < view.today:
                f.append(Finding(code="OVERDUE", severity=Severity.LOW, message=f"Overdue since {inv.due_date.isoformat()}."))

        # 10. on-chain policy and liquidity
        if amount is not None and vendor:
            units = to_units(amount)
            self._limits(f, plan, units, view, payee_state)

        action = route(f)
        return Decision(
            kind="invoice",
            subject=f"{inv.invoice_no or '?'} from {inv.vendor_name or 'unknown issuer'}",
            action=action,
            vendor_id=vendor.id if vendor else None,
            payee=vendor.wallet if vendor else None,
            amount=amount,
            ref=ref,
            po_id=po.id if po else None,
            findings=f,
            risk_score=risk_score(f),
            plan=plan if action in (Action.EXECUTE, Action.REQUEST_APPROVAL) else [],
            decided_at=view.now,
        )

    def match_po(self, vendor: Vendor, inv: Invoice, amount: Decimal, ref: str | None,
                 po_usage: dict[str, list[str]]) -> tuple[PurchaseOrder | None, list[Finding]]:
        """Match an invoice to an open purchase order of the SAME vendor with an amount inside tolerance.

        A PO number printed on the invoice is a claim, not proof: it must exist, belong to this vendor, be open,
        have call-offs left and match the amount. Without a reference we look for an open PO by vendor + amount.
        Recurring obligations (vendors.json) are their own authority and are paid by `evaluate_obligation`.
        """
        tol = self.registry.po_tolerance_pct

        def left(po: PurchaseOrder) -> int:
            used = [r for r in po_usage.get(po.id, []) if r != ref]
            return po.invoices_allowed - len(used)

        def within(po: PurchaseOrder) -> bool:
            return abs(amount - po.amount) <= po.amount * tol / Decimal(100)

        def matched(po: PurchaseOrder) -> Finding:
            return Finding(code="PO_MATCHED", severity=Severity.INFO,
                           message=f"Matches open purchase order {po.id} ({po.description}).", evidence={"po": po.id})

        if inv.po_ref:
            po = self.registry.po_by_id(inv.po_ref)
            if po is None or po.vendor_id != vendor.id or po.status != "open" or left(po) <= 0:
                why = ("that PO number does not exist" if po is None
                       else "that PO belongs to another vendor" if po.vendor_id != vendor.id
                       else "that PO is closed or fully invoiced")
                return None, [Finding(code="PO_REFERENCE_INVALID", severity=Severity.HIGH,
                                      message=f"Invoice cites purchase order {inv.po_ref}, but {why}; a human must confirm the order.",
                                      evidence={"po_ref": inv.po_ref})]
            if not within(po):
                return None, [Finding(code="PO_AMOUNT_MISMATCH", severity=Severity.HIGH,
                                      message=f"Invoice amount {amount} is outside the {tol}% tolerance of {po.id} ({po.amount}).",
                                      evidence={"po": po.id, "po_amount": str(po.amount), "invoice_amount": str(amount)})]
            return po, [matched(po)]
        cands = [po for po in self.registry.open_pos(vendor.id) if left(po) > 0 and within(po)]
        if cands:
            po = min(cands, key=lambda p: (abs(amount - p.amount), p.id))
            return po, [matched(po)]
        return None, [Finding(code="NO_MATCHING_PO", severity=Severity.HIGH,
                              message="No open purchase order from this vendor matches this amount, so it may be for goods "
                                      "never ordered. A human must confirm before paying.",
                              evidence={"open_pos": [f"{p.id}={p.amount}" for p in self.registry.open_pos(vendor.id) if left(p) > 0]})]

    def evaluate_obligation(self, vendor: Vendor, amount: Decimal, ref: str, subject: str, view: VaultView,
                            payee_state: dict | None, ref_used_onchain: bool) -> Decision:
        f: list[Finding] = []
        plan: list[str] = []
        f += self.registry.screen([vendor.wallet.lower()])
        if ref_used_onchain:
            f.append(Finding(code="DUPLICATE_INVOICE", severity=Severity.CRITICAL, message="Obligation already paid this period."))
        self._limits(f, plan, to_units(amount), view, payee_state)
        action = route(f)
        return Decision(kind="obligation", subject=subject, action=action, vendor_id=vendor.id, payee=vendor.wallet,
                        amount=amount, ref=ref, findings=f, risk_score=risk_score(f),
                        plan=plan if action in (Action.EXECUTE, Action.REQUEST_APPROVAL) else [], decided_at=view.now)

    @staticmethod
    def _limits(f: list[Finding], plan: list[str], units: int, view: VaultView, payee_state: dict | None) -> None:
        if view.paused:
            f.append(Finding(code="VAULT_PAUSED", severity=Severity.INFO, message="Vault is paused by the circuit breaker."))
        if payee_state is not None and not payee_state.get("allowed"):
            f.append(
                Finding(
                    code="PAYEE_NOT_ONCHAIN",
                    severity=Severity.CRITICAL,
                    message="Vendor is not registered as a payee in the vault; the owner must onboard it first.",
                )
            )
        elif payee_state is not None and view.now < payee_state.get("activeFrom", 0):
            f.append(
                Finding(
                    code="PAYEE_COOLING_DOWN",
                    severity=Severity.INFO,
                    message="New payee is still in its cooling-off period; owner approval required.",
                )
            )
        if units > view.hard_cap:
            f.append(
                Finding(
                    code="EXCEEDS_HARD_CAP",
                    severity=Severity.CRITICAL,
                    message=f"Amount exceeds the absolute cap of {from_units(view.hard_cap)} per payment.",
                )
            )
        elif units > view.auto_limit:
            f.append(
                Finding(
                    code="ABOVE_AUTO_LIMIT",
                    severity=Severity.INFO,
                    message=f"Amount above the agent's solo limit of {from_units(view.auto_limit)}; maker-checker applies.",
                )
            )
        elif units > view.daily_remaining:
            f.append(
                Finding(
                    code="DAILY_LIMIT_REACHED",
                    severity=Severity.INFO,
                    message=f"Only {from_units(view.daily_remaining)} left in today's solo budget; routed to approval.",
                )
            )
        if units > view.liquid + view.reserve:
            f.append(
                Finding(
                    code="INSUFFICIENT_FUNDS",
                    severity=Severity.INFO,
                    message="Treasury cannot cover this payment; holding until funds arrive.",
                )
            )
        elif units > view.liquid:
            need = units - view.liquid
            plan.append(f"withdraw {from_units(need)} from reserve before paying")
            f.append(
                Finding(
                    code="RESERVE_WITHDRAWAL",
                    severity=Severity.INFO,
                    message=f"Liquid cash is short by {from_units(need)}; withdrawing from the reserve first.",
                    evidence={"units": need},
                )
            )
