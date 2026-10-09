"""KendaliAgent — orchestrates understanding (LLM/NLU), deciding (policy) and acting (vault).

Principle: the LLM proposes, the policy decides, the contract enforces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from web3 import Web3

from . import nlu
from .audit import AuditLog, decision_hash
from .chain import Chain, TxReverted
from .config import Settings
from .explain import explain
from .invoices import load_invoice
from .llm import LLMClient, compare_extractions
from .models import Action, Decision, ExecutionResult, Finding, Intent, Severity
from .money import fmt, from_units, to_units
from .policy import PAY_AHEAD_DAYS, PolicyEngine, VaultView, payment_ref
from .registry import Registry
from .treasury import plan_rebalance

DECISION_KIND = {"Blocked": 0, "Held": 1, "Escalated": 2, "Info": 3}
REROUTABLE = {"ExceedsDailyLimit", "PayeeCoolingDown", "ExceedsAutoLimit"}

HELP_EN = (
    "I can: process the invoice inbox, pay a specific invoice, pay recurring obligations, keep a runway "
    "and park idle cash in the reserve, report cash, show pending approvals, explain past payments, "
    "and pause the vault in an emergency. I cannot approve my own proposals, change limits, add payees, "
    "pay raw addresses or grant token allowances. Those belong to the owner."
)
HELP_ID = (
    "Saya bisa: memproses kotak masuk invoice, membayar invoice tertentu, membayar tagihan rutin, menjaga "
    "runway dan memarkir kas menganggur ke cadangan, melaporkan kas, menampilkan persetujuan tertunda, "
    "menjelaskan pembayaran lalu, dan menjeda vault saat darurat. Saya tidak bisa menyetujui usulan saya "
    "sendiri, mengubah batas, menambah penerima, membayar alamat mentah, atau memberi izin token. "
    "Itu wewenang pemilik."
)
REFUSAL_TEXT = {
    "AGENT_CANNOT_APPROVE": ("Maker-checker: I can propose payments but only the owner can approve them, from the owner console.",
                             "Maker-checker: saya hanya bisa mengusulkan; persetujuan hanya oleh pemilik lewat konsol pemilik."),
    "AGENT_CANNOT_CHANGE_POLICY": ("Policy (limits, payees, unpausing) is owner-only and loosening is time-locked on-chain.",
                                   "Kebijakan (batas, penerima, membuka jeda) hanya untuk pemilik, dan pelonggaran dikunci waktu on-chain."),
    "RAW_ADDRESS_NOT_ALLOWED": ("I only pay KYB-verified vendors from the vendor master, never raw addresses from chat or documents.",
                                "Saya hanya membayar vendor terverifikasi KYB, bukan alamat mentah dari chat atau dokumen."),
    "TOKEN_APPROVAL_NOT_SUPPORTED": ("The vault has no function to grant token allowances; this request cannot be executed.",
                                     "Vault tidak punya fungsi untuk memberi izin token; permintaan ini tidak bisa dijalankan."),
    "IDENTITY_CLAIM_NOT_ACCEPTED": ("Identity claims in chat are not authentication. Owner actions are signed in the owner console.",
                                    "Klaim identitas di chat bukan autentikasi. Tindakan pemilik ditandatangani di konsol pemilik."),
}


@dataclass
class Reply:
    text: str
    intent: Intent
    results: list[ExecutionResult] = field(default_factory=list)


class State:
    """Local working state (inbox ledger). The chain + audit log remain the source of truth."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"invoices": {}, "sources": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, default=str), encoding="utf-8")


class KendaliAgent:
    def __init__(self, settings: Settings, chain: Chain, llm: LLMClient | None = None,
                 registry: Registry | None = None, run_dir: Path | None = None):
        self.settings = settings
        self.chain = chain
        self.llm = llm
        self.registry = registry or Registry.load(settings.data_dir)
        self.policy = PolicyEngine(self.registry)
        self.run_dir = run_dir or settings.runs_dir / self.run_tag(settings, chain)
        self.audit = AuditLog(self.run_dir / "audit.jsonl")
        self.state = State(self.run_dir / "state.json")
        self.inbox = settings.data_dir / "invoices" / "inbox"

    @staticmethod
    def run_tag(settings: Settings, chain: Chain) -> str:
        """Working state is bound to one specific deployment, so a redeploy never inherits a stale ledger."""
        dep = chain.deployment or {}
        tag = f"{settings.network}-{chain.chain_id}"
        if dep.get("vault"):
            tag += f"-{dep['vault'][2:10].lower()}-{dep.get('deployed_at', 0)}"
        return tag

    # ------------------------------------------------------------------ chain views
    def view(self) -> VaultView:
        lim = self.chain.limits()
        return VaultView(
            now=self.chain.now(),
            paused=self.chain.paused(),
            auto_limit=lim["autoLimit"],
            daily_remaining=self.chain.remaining_daily(),
            hard_cap=lim["hardCap"],
            liquid=self.chain.liquid(),
            reserve=self.chain.reserve_assets(),
        )

    def today(self) -> date:
        return datetime.fromtimestamp(self.chain.now(), tz=timezone.utc).date()

    # ------------------------------------------------------------------ invoices
    def process_invoice(self, path: Path, force: bool = False, lang: str = "en",
                        pay_ahead_days: int = PAY_AHEAD_DAYS) -> ExecutionResult:
        inv = load_invoice(path)
        llm_diffs: list[str] = []
        llm_flag = False
        llm_used = False
        llm_finding: Finding | None = None
        if self.llm is not None:
            try:
                le = self.llm.extract_invoice(inv.raw_text)
                llm_diffs = compare_extractions(inv, le)
                llm_flag = bool(le.get("embedded_instructions"))
                llm_used = True
            except Exception as e:  # the agent degrades to the deterministic path, it never fails open
                llm_finding = Finding(code="LLM_UNAVAILABLE", severity=Severity.INFO,
                                      message=f"LLM cross-check unavailable ({type(e).__name__}); deterministic extraction only.")
        vendor, _ = self.registry.resolve(inv.vendor_name, inv.registration_no)
        ref = payment_ref(vendor.id, inv.invoice_no) if vendor and inv.invoice_no else None
        ref_used = self.chain.ref_used(ref) if ref else False
        ledger_status = self.state.data["invoices"].get(ref, {}).get("status") if ref else None
        payee_state = self.chain.payee(vendor.wallet) if vendor else None
        d = self.policy.evaluate_invoice(inv, self.view(), payee_state, ref_used, ledger_status, llm_diffs, llm_flag,
                                         force=force, pay_ahead_days=pay_ahead_days)
        if llm_finding:
            d.findings.append(llm_finding)
        d.llm_used = llm_used
        callback = vendor.callback_contact if vendor else ""
        d.explanation = explain(d, lang, callback)
        result = self.execute(d)
        if ref:
            self.state.data["invoices"][ref] = {
                "status": result.decision.action.value,
                "invoice_no": inv.invoice_no,
                "vendor_id": vendor.id if vendor else None,
                "amount": str(inv.total) if inv.total is not None else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "source": path.name,
                "decision_hash": result.decision_hash,
                "proposal_id": result.proposal_id,
                "tx": result.tx_hashes,
            }
        self.state.data["sources"][path.name] = {"status": result.decision.action.value, "decision_hash": result.decision_hash}
        self.state.save()
        return result

    def process_inbox(self, inbox: Path | None = None, due_within_days: int | None = None, lang: str = "en") -> list[ExecutionResult]:
        inbox = inbox or self.inbox
        results = []
        final = {Action.EXECUTE.value, Action.REQUEST_APPROVAL.value, Action.BLOCK.value}
        ahead = PAY_AHEAD_DAYS if due_within_days is None else due_within_days
        for p in sorted(inbox.iterdir()):
            if p.suffix.lower() not in {".txt", ".md", ".pdf", ".json"}:
                continue
            if self.state.data["sources"].get(p.name, {}).get("status") in final:
                continue
            results.append(self.process_invoice(p, lang=lang, pay_ahead_days=ahead))
        return results

    def find_invoice(self, invoice_no: str, inbox: Path | None = None) -> Path | None:
        inbox = inbox or self.inbox
        for p in sorted(inbox.iterdir()):
            if p.suffix.lower() not in {".txt", ".md", ".pdf", ".json"}:
                continue
            inv = load_invoice(p)
            if inv.invoice_no and inv.invoice_no.upper() == invoice_no.upper():
                return p
        return None

    # ------------------------------------------------------------------ recurring obligations
    def run_obligations(self, lang: str = "en") -> list[ExecutionResult]:
        today = self.today()
        out = []
        for o in self.registry.obligations:
            if today.day != o.day_of_month:
                continue
            vendor = self.registry.vendors[o.vendor_id]
            ref = Web3.to_hex(Web3.keccak(text=f"{o.id}|{today:%Y-%m}"))
            d = self.policy.evaluate_obligation(vendor, o.amount, ref, f"{o.description} ({today:%Y-%m})", self.view(),
                                                self.chain.payee(vendor.wallet), self.chain.ref_used(ref))
            d.explanation = explain(d, lang, vendor.callback_contact)
            out.append(self.execute(d))
        return out

    # ------------------------------------------------------------------ treasury
    def upcoming_needs(self, days: int) -> list[tuple[str, Decimal]]:
        today = self.today()
        needs = []
        for ref, rec in self.state.data["invoices"].items():
            if rec.get("status") == Action.HOLD.value and rec.get("amount") and rec.get("due_date"):
                if (date.fromisoformat(rec["due_date"]) - today).days <= days:
                    needs.append((ref, Decimal(rec["amount"])))
        for p in self.chain.proposals():
            if p["status"] == "Pending":
                needs.append((p["ref"], from_units(p["amount"])))
        return needs

    def rebalance(self, runway_days: int | None = None, lang: str = "en") -> ExecutionResult:
        days = runway_days or 14

        def is_paid(o, day) -> bool:
            return self.chain.ref_used(Web3.to_hex(Web3.keccak(text=f"{o.id}|{day:%Y-%m}")))

        d = plan_rebalance(self.registry, self.view(), self.upcoming_needs(days), days, is_paid)
        d.explanation = explain(d, lang)
        return self.execute(d)

    # ------------------------------------------------------------------ execution
    def execute(self, d: Decision) -> ExecutionResult:
        """Simulate, then sign. Every anchored decision carries its hash on-chain."""
        c = self.chain
        tx_hashes: list[str] = []
        onchain = "none"
        proposal_id = None
        error = None
        dh = decision_hash(d)
        try:
            if d.kind in ("invoice", "obligation") and d.action in (Action.EXECUTE, Action.REQUEST_APPROVAL):
                for f in d.findings:
                    if f.code == "RESERVE_WITHDRAWAL":
                        fn_w = c.vault.functions.withdrawFromReserve(int(f.evidence["units"]), bytes.fromhex(dh[2:]))
                        sim_w = c.simulate(c.agent, fn_w)
                        if not sim_w.ok:
                            raise TxReverted("(simulation)", f"reserve withdrawal: {sim_w.describe()}")
                        tx_hashes.append(Web3.to_hex(c.send(c.agent, fn_w)["transactionHash"]))
                to = Web3.to_checksum_address(d.payee)
                units = to_units(d.amount)
                ref_b = bytes.fromhex(d.ref[2:])
                fn = (c.vault.functions.pay if d.action == Action.EXECUTE else c.vault.functions.propose)(
                    to, units, ref_b, bytes.fromhex(dh[2:]))
                sim = c.simulate(c.agent, fn)
                if not sim.ok and d.action == Action.EXECUTE and sim.error in REROUTABLE:
                    d.findings.append(Finding(code="SIMULATION_REROUTE", severity=Severity.INFO,
                                              message=f"Pre-sign simulation: {sim.error}; rerouted to owner approval."))
                    d.action = Action.REQUEST_APPROVAL
                    d.explanation = explain(d)
                    dh = decision_hash(d)
                    fn = c.vault.functions.propose(to, units, ref_b, bytes.fromhex(dh[2:]))
                    sim = c.simulate(c.agent, fn)
                if not sim.ok:
                    d.findings.append(Finding(code="SIMULATION_FAILED", severity=Severity.CRITICAL,
                                              message=f"Pre-sign simulation rejected the transaction: {sim.describe()}."))
                    d.action = Action.BLOCK
                    d.explanation = explain(d)
                    dh = decision_hash(d)
                    receipt = c.send(c.agent, c.vault.functions.commitDecision(bytes.fromhex(dh[2:]), DECISION_KIND["Blocked"]))
                    tx_hashes.append(Web3.to_hex(receipt["transactionHash"]))
                    onchain = "DecisionCommitted"
                else:
                    receipt = c.send(c.agent, fn)
                    tx_hashes.append(Web3.to_hex(receipt["transactionHash"]))
                    if d.action == Action.EXECUTE:
                        onchain = "AutoPaid"
                    else:
                        ev = c.vault.events.ProposalCreated().process_receipt(receipt)
                        proposal_id = int(ev[0]["args"]["id"]) if ev else None
                        onchain = f"ProposalCreated#{proposal_id}"
            elif d.kind == "treasury" and d.action == Action.EXECUTE and d.amount:
                units = to_units(d.amount)
                if d.plan and d.plan[0].startswith("sweep"):
                    fn = c.vault.functions.sweepToReserve(units, bytes.fromhex(dh[2:]))
                    onchain = "ReserveDeposited"
                else:
                    fn = c.vault.functions.withdrawFromReserve(units, bytes.fromhex(dh[2:]))
                    onchain = "ReserveWithdrawn"
                sim = c.simulate(c.agent, fn)
                if not sim.ok:
                    raise TxReverted("(simulation)", sim.describe())
                tx_hashes.append(Web3.to_hex(c.send(c.agent, fn)["transactionHash"]))
            elif d.action in (Action.BLOCK, Action.REFUSE):
                kind = DECISION_KIND["Blocked"] if d.action == Action.BLOCK else DECISION_KIND["Escalated"]
                receipt = c.send(c.agent, c.vault.functions.commitDecision(bytes.fromhex(dh[2:]), kind))
                tx_hashes.append(Web3.to_hex(receipt["transactionHash"]))
                onchain = "DecisionCommitted"
            elif d.kind == "instruction" and d.action == Action.EXECUTE and "pause vault" in d.plan:
                receipt = c.send(c.agent, c.vault.functions.commitDecision(bytes.fromhex(dh[2:]), DECISION_KIND["Info"]))
                tx_hashes.append(Web3.to_hex(receipt["transactionHash"]))
                tx_hashes.append(Web3.to_hex(c.send(c.agent, c.vault.functions.pause())["transactionHash"]))
                onchain = "DecisionCommitted+Paused"
        except TxReverted as e:
            error = e.error
        self.audit.append(d, dh, tx_hashes, onchain, proposal_id, c.chain_id, error)
        return ExecutionResult(decision=d, decision_hash=dh, tx_hashes=tx_hashes, onchain=onchain,
                               proposal_id=proposal_id, error=error)

    # ------------------------------------------------------------------ conversation
    def understand(self, message: str) -> Intent:
        baseline = nlu.parse(message)
        if baseline.name == "REFUSE":
            return baseline  # mandate checks are deterministic and cannot be talked around
        if self.llm is not None:
            try:
                intent = self.llm.parse_intent(message)
                if intent is not None:
                    intent.language = baseline.language
                    return intent
            except Exception:
                pass
        return baseline

    def handle(self, message: str) -> Reply:
        intent = self.understand(message)
        lang = intent.language
        i = 1 if lang == "id" else 0
        n = intent.name
        if n == "REFUSE":
            reason = intent.params.get("reason", "AGENT_CANNOT_CHANGE_POLICY")
            text = REFUSAL_TEXT.get(reason, REFUSAL_TEXT["AGENT_CANNOT_CHANGE_POLICY"])[i]
            d = Decision(kind="instruction", subject=f"chat request: {message[:120]}", action=Action.REFUSE,
                         findings=[Finding(code=reason, severity=Severity.HIGH, message=text)], risk_score=30,
                         decided_at=self.chain.now(), explanation=text)
            r = self.execute(d)
            return Reply(text=f"{text}\n(anchored on-chain: {r.tx_hashes[0] if r.tx_hashes else 'n/a'})", intent=intent, results=[r])
        if n == "PROCESS_INBOX":
            results = self.process_inbox(due_within_days=intent.params.get("due_within_days"), lang=lang)
            if not results:
                return Reply(text="Inbox is empty or already processed." if i == 0 else "Kotak masuk kosong atau sudah diproses.", intent=intent)
            return Reply(text=self.summarize(results, lang), intent=intent, results=results)
        if n == "PAY_INVOICE":
            p = self.find_invoice(intent.params.get("invoice_no", ""))
            if p is None:
                return Reply(text="Invoice not found in the inbox." if i == 0 else "Invoice tidak ditemukan di kotak masuk.", intent=intent)
            r = self.process_invoice(p, force=True, lang=lang)
            return Reply(text=r.decision.explanation, intent=intent, results=[r])
        if n == "RUN_OBLIGATIONS":
            results = self.run_obligations(lang)
            if not results:
                return Reply(text="No recurring obligations due today." if i == 0 else "Tidak ada tagihan rutin jatuh tempo hari ini.", intent=intent)
            return Reply(text=self.summarize(results, lang), intent=intent, results=results)
        if n == "REBALANCE_TREASURY":
            r = self.rebalance(intent.params.get("runway_days"), lang)
            return Reply(text=r.decision.explanation, intent=intent, results=[r])
        if n == "CASH_REPORT":
            return Reply(text=self.cash_report(lang), intent=intent)
        if n == "LIST_PENDING":
            pend = [p for p in self.chain.proposals() if p["status"] == "Pending"]
            if not pend:
                return Reply(text="No pending approvals." if i == 0 else "Tidak ada persetujuan tertunda.", intent=intent)
            lines = [f"#{p['id']}: {fmt(p['amount'])} to {self._name(p['to'])}" for p in pend]
            return Reply(text="\n".join(lines), intent=intent)
        if n == "AUDIT_QUERY":
            return Reply(text=self.audit_answer(intent.params.get("vendor") or self.vendor_mentioned(message), lang), intent=intent)
        if n == "PAUSE":
            d = Decision(kind="instruction", subject="emergency pause requested by owner chat", action=Action.EXECUTE,
                         plan=["pause vault"], decided_at=self.chain.now(),
                         explanation="Vault paused. Only the owner can unpause." if i == 0 else "Vault dijeda. Hanya pemilik yang bisa membuka jeda.")
            r = self.execute(d)
            return Reply(text=d.explanation, intent=intent, results=[r])
        return Reply(text=HELP_ID if i else HELP_EN, intent=intent)

    # ------------------------------------------------------------------ reporting
    def vendor_mentioned(self, message: str) -> str | None:
        """Return the legal name of a vendor mentioned in free text (any distinctive name token)."""
        low = message.lower()
        generic = {"packaging", "logistics", "indonesia", "ltd", "pte", "warehouse", "equipment", "partners", "trade",
                   "global", "city", "lion", "cooperative", "koperasi", "kopi", "tani"}
        for v in self.registry.vendors.values():
            for name in [v.legal_name, *v.aliases]:
                for tok in name.lower().replace(",", " ").replace(".", " ").split():
                    if len(tok) >= 4 and tok not in generic and tok in low:
                        return v.legal_name
        return None

    def _name(self, address: str) -> str:
        v = self.registry.by_wallet(address)
        return v.legal_name if v else address

    def summarize(self, results: list[ExecutionResult], lang: str = "en") -> str:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.decision.action.value] = counts.get(r.decision.action.value, 0) + 1
        head = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        body = "\n\n".join(r.decision.explanation + (f"\ntx: {', '.join(r.tx_hashes)}" if r.tx_hashes else "") for r in results)
        return f"{head}\n\n{body}"

    def cash_report(self, lang: str = "en") -> str:
        v = self.view()
        pend = [p for p in self.chain.proposals() if p["status"] == "Pending"]
        if lang == "id":
            return (f"Kas likuid {fmt(v.liquid)}, cadangan {fmt(v.reserve)}, total {fmt(v.liquid + v.reserve)}. "
                    f"Sisa batas mandiri hari ini {fmt(v.daily_remaining)}. Usulan menunggu persetujuan: {len(pend)}."
                    + (" Vault sedang DIJEDA." if v.paused else ""))
        return (f"Liquid {fmt(v.liquid)}, reserve {fmt(v.reserve)}, total {fmt(v.liquid + v.reserve)}. "
                f"Solo budget left today {fmt(v.daily_remaining)}. Proposals awaiting approval: {len(pend)}."
                + (" Vault is PAUSED." if v.paused else ""))

    def audit_answer(self, vendor_query: str | None, lang: str = "en") -> str:
        entries = self.audit.entries()
        rows = []
        for e in entries:
            d = e["decision"]
            if d["kind"] not in ("invoice", "obligation"):
                continue
            if vendor_query:
                v = self.registry.vendors.get(d.get("vendor_id") or "")
                hay = (d["subject"] + " " + (v.legal_name if v else "") + " " + " ".join(v.aliases if v else [])).lower()
                if vendor_query.lower() not in hay:
                    continue
            rows.append(f"- {d['action']}: {d['subject']} ({d.get('amount')}) tx={','.join(e['tx_hashes']) or '-'}\n  "
                        + d["explanation"].split("\n")[1 if '\n' in d["explanation"] else 0])
        if not rows:
            return "No matching payments in the audit trail." if lang != "id" else "Tidak ada pembayaran yang cocok di jejak audit."
        return "\n".join(rows)

    def status(self) -> dict:
        v = self.view()
        lim = self.chain.limits()
        return {
            "network": self.settings.network,
            "chain_id": self.chain.chain_id,
            "vault": self.chain.vault.address,
            "now": datetime.fromtimestamp(v.now, tz=timezone.utc).isoformat(),
            "paused": v.paused,
            "liquid": str(from_units(v.liquid)),
            "reserve": str(from_units(v.reserve)),
            "auto_limit": str(from_units(lim["autoLimit"])),
            "daily_auto_limit": str(from_units(lim["dailyAutoLimit"])),
            "daily_remaining": str(from_units(v.daily_remaining)),
            "hard_cap": str(from_units(lim["hardCap"])),
            "pending_proposals": len([p for p in self.chain.proposals() if p["status"] == "Pending"]),
            "audit_entries": len(self.audit.entries()),
            "llm": bool(self.llm),
        }


class OwnerConsole:
    """Owner-side actions, signed with the OWNER key (a separate device/multisig in production)."""

    def __init__(self, chain: Chain, registry: Registry):
        self.chain = chain
        self.registry = registry

    def approve(self, proposal_id: int) -> str:
        r = self.chain.send(self.chain.owner, self.chain.vault.functions.approveProposal(proposal_id))
        return Web3.to_hex(r["transactionHash"])

    def reject(self, proposal_id: int, reason: str) -> str:
        r = self.chain.send(self.chain.owner, self.chain.vault.functions.rejectProposal(proposal_id, Web3.keccak(text=reason)))
        return Web3.to_hex(r["transactionHash"])

    def unpause(self) -> str:
        return Web3.to_hex(self.chain.send(self.chain.owner, self.chain.vault.functions.unpause())["transactionHash"])

    def add_payee(self, vendor_id: str) -> str:
        v = self.registry.vendors[vendor_id]
        r = self.chain.send(self.chain.owner, self.chain.vault.functions.addPayee(v.wallet, self.registry.kyb_hash(v)))
        return Web3.to_hex(r["transactionHash"])
