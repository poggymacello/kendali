"""Vendor master (KYB-verified payees), recurring obligations and the screening blocklist."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from web3 import Web3

from .models import Finding, Obligation, Severity, Vendor
from .security import fold_confusables, is_lookalike, normalize_name


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
        return cls(vendors=vendors, obligations=obligations, blocklist=blocklist, business=raw.get("business", {}))

    # ------------------------------------------------------------------ vendors
    def kyb_hash(self, v: Vendor) -> bytes:
        """Hash of the off-chain KYB record anchored on-chain when the payee is added."""
        record = f"{v.id}|{v.legal_name}|{v.registration_no}|{v.country}|{v.wallet.lower()}|{v.kyb_verified_on.isoformat()}"
        return hashlib.sha256(record.encode()).digest()

    def by_wallet(self, address: str) -> Vendor | None:
        a = address.lower()
        return next((v for v in self.vendors.values() if v.wallet.lower() == a), None)

    def resolve(self, name: str | None, registration_no: str | None) -> tuple[Vendor | None, list[Finding]]:
        """Resolve an invoice issuer to a vendor in the master. Homoglyph tricks are reported, not forgiven."""
        findings: list[Finding] = []
        if not name:
            return None, [Finding(code="MISSING_VENDOR", severity=Severity.CRITICAL, message="Invoice has no issuer.")]
        _, had_confusables = fold_confusables(name)
        target = normalize_name(name)
        match = None
        for v in self.vendors.values():
            names = [v.legal_name, *v.aliases]
            if any(normalize_name(n) == target for n in names):
                match = v
                break
        if match is None and registration_no:
            match = next((v for v in self.vendors.values() if v.registration_no == registration_no.strip()), None)
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
        if match and registration_no and registration_no.strip() != match.registration_no:
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
