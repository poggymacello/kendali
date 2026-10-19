"""Vendor master (KYB-verified payees), open purchase orders, recurring obligations and the screening blocklist."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from web3 import Web3

from .models import Finding, Obligation, PurchaseOrder, Severity, Vendor
from .security import fold_confusables, is_lookalike, normalize_name


def norm_reg(reg: str) -> str:
    """'UEN-201912345K', 'UEN: 201912345K' and '201912345k' all compare equal."""
    s = reg.strip().upper()
    s = re.sub(r"^(UEN|NIB|USCC|NPWP|REG)\b[\s:.\-]*", "", s)
    return re.sub(r"[^A-Z0-9]", "", s)


@dataclass
class BlocklistEntry:
    address: str
    source: str
    reason: str


@dataclass
class Registry:
    vendors: dict[str, Vendor]
    obligations: list[Obligation]
    blocklist: dict[str, BlocklistEntry]
    business: dict = field(default_factory=dict)
    purchase_orders: list[PurchaseOrder] = field(default_factory=list)
    po_tolerance_pct: Decimal = Decimal("2")

    @classmethod
    def load(cls, data_dir: Path) -> "Registry":
        raw = json.loads((data_dir / "vendors.json").read_text(encoding="utf-8"))
        vendors = {}
        for v in raw["vendors"]:
            v["wallet"] = Web3.to_checksum_address(v["wallet"])
            vendors[v["id"]] = Vendor(**v)
        obligations = [Obligation(**o) for o in raw.get("obligations", [])]
        bl_raw = json.loads((data_dir / "screening" / "blocklist.json").read_text(encoding="utf-8"))
        blocklist = {
            e["address"].lower(): BlocklistEntry(e["address"].lower(), e["source"], e["reason"]) for e in bl_raw["entries"]
        }
        # Open purchase orders / expected bills. Missing file = empty register = every invoice needs a human (fail closed).
        pos: list[PurchaseOrder] = []
        tol = Decimal("2")
        po_path = data_dir / "purchase_orders.json"
        if po_path.exists():
            po_raw = json.loads(po_path.read_text(encoding="utf-8"))
            pos = [PurchaseOrder(**po) for po in po_raw.get("purchase_orders", [])]
            tol = Decimal(str(po_raw.get("tolerance_pct", "2")))
        return cls(vendors=vendors, obligations=obligations, blocklist=blocklist, business=raw.get("business", {}),
                   purchase_orders=pos, po_tolerance_pct=tol)

    # ------------------------------------------------------------------ purchase orders
    def po_by_id(self, po_id: str) -> PurchaseOrder | None:
        key = re.sub(r"[^A-Z0-9]", "", po_id.upper())
        return next((po for po in self.purchase_orders if re.sub(r"[^A-Z0-9]", "", po.id.upper()) == key), None)

    def open_pos(self, vendor_id: str) -> list[PurchaseOrder]:
        return [po for po in self.purchase_orders if po.vendor_id == vendor_id and po.status == "open"]

    # ------------------------------------------------------------------ vendors
    def kyb_hash(self, v: Vendor) -> bytes:
        """Hash of the off-chain KYB record anchored on-chain when the payee is added."""
        record = f"{v.id}|{v.legal_name}|{v.registration_no}|{v.country}|{v.wallet.lower()}|{v.kyb_verified_on.isoformat()}"
        return hashlib.sha256(record.encode()).digest()

    def by_wallet(self, address: str) -> Vendor | None:
        a = address.lower()
        return next((v for v in self.vendors.values() if v.wallet.lower() == a), None)

    def by_registration(self, registration_no: str | None) -> Vendor | None:
        if not registration_no:
            return None
        key = norm_reg(registration_no)
        return next((v for v in self.vendors.values() if norm_reg(v.registration_no) == key), None)

    def resolve(self, name: str | None, registration_no: str | None) -> tuple[Vendor | None, list[Finding]]:
        """Resolve an invoice issuer to a vendor in the master. Homoglyph tricks are reported, not forgiven."""
        findings: list[Finding] = []
        if not name:
            match = self.by_registration(registration_no) if registration_no else None
            if match is None:
                return None, [Finding(code="MISSING_VENDOR", severity=Severity.CRITICAL, message="Invoice has no issuer.")]
            return match, [
                Finding(
                    code="VENDOR_NAME_UNREAD",
                    severity=Severity.HIGH,
                    message="Issuer name could not be read; vendor identified by registration number only, so a human confirms.",
                    evidence={"registration_no": registration_no, "master_name": match.legal_name},
                )
            ]
        _, had_confusables = fold_confusables(name)
        target = normalize_name(name)
        match = None
        for v in self.vendors.values():
            names = [v.legal_name, *v.aliases]
            if any(normalize_name(n) == target for n in names):
                match = v
                break
        if match is None and registration_no:
            match = self.by_registration(registration_no)
            if match:
                findings.append(
                    Finding(
                        code="VENDOR_NAME_MISMATCH",
                        severity=Severity.HIGH,
                        message="Issuer name differs from the vendor master although the registration number matches.",
                        evidence={"invoice_name": name, "master_name": match.legal_name},
                    )
                )
        if match and had_confusables:
            findings.append(
                Finding(
                    code="HOMOGLYPH_IMPERSONATION",
                    severity=Severity.CRITICAL,
                    message="Issuer name uses look-alike non-Latin characters to imitate a known vendor.",
                    evidence={"imitates": match.legal_name},
                )
            )
        if match and registration_no and norm_reg(registration_no) != norm_reg(match.registration_no):
            findings.append(
                Finding(
                    code="REGISTRATION_MISMATCH",
                    severity=Severity.HIGH,
                    message="Registration number on the invoice does not match the KYB record.",
                    evidence={"invoice": registration_no, "kyb": match.registration_no},
                )
            )
        if match is None:
            findings.append(
                Finding(
                    code="UNKNOWN_VENDOR",
                    severity=Severity.CRITICAL,
                    message="Issuer is not in the KYB-verified vendor master. Onboarding by the owner is required.",
                    evidence={"issuer": name},
                )
            )
        return match, findings

    # ------------------------------------------------------------------ screening
    def screen(self, addresses: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for a in addresses:
            e = self.blocklist.get(a.lower())
            if e:
                findings.append(
                    Finding(
                        code="SANCTIONS_OR_SCAM_HIT",
                        severity=Severity.CRITICAL,
                        message=f"Address appears on the screening list ({e.source}): {e.reason}.",
                        evidence={"address": a, "source": e.source},
                    )
                )
        return findings

    def poisoning(self, candidate: str) -> list[Finding]:
        for v in self.vendors.values():
            if is_lookalike(candidate, v.wallet):
                return [
                    Finding(
                        code="ADDRESS_POISONING",
                        severity=Severity.CRITICAL,
                        message="Address imitates a known vendor wallet (same visible prefix and suffix).",
                        evidence={"candidate": candidate, "imitates": v.wallet, "vendor": v.legal_name},
                    )
                ]
        return []

    def obligation_due_dates(self, start: date, horizon_days: int) -> list[tuple[Obligation, date]]:
        """Occurrences of recurring obligations within [start, start + horizon]."""
        out = []
        from datetime import timedelta

        end = start + timedelta(days=horizon_days)
        d = start
        while d <= end:
            for o in self.obligations:
                if d.day == o.day_of_month:
                    out.append((o, d))
            d += timedelta(days=1)
        return out

    def total(self, items: list[tuple[Obligation, date]]) -> Decimal:
        return sum((o.amount for o, _ in items), Decimal(0))
