"""Typed data model shared by every layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(str, Enum):
    EXECUTE = "EXECUTE"  # agent pays alone, inside on-chain auto limits
    REQUEST_APPROVAL = "REQUEST_APPROVAL"  # on-chain proposal; owner must approve (maker-checker)
    HOLD = "HOLD"  # legitimate but not now (not due, insufficient funds, paused)
    BLOCK = "BLOCK"  # refused; anchored on-chain as a blocked decision
    REFUSE = "REFUSE"  # instruction outside the agent's mandate
    INFO = "INFO"  # read-only answer


class Finding(BaseModel):
    code: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class Vendor(BaseModel):
    id: str
    legal_name: str
    aliases: list[str] = Field(default_factory=list)
    registration_no: str
    country: str
    category: str
    wallet: str
    kyb_verified_on: date
    typical_min: Decimal
    typical_max: Decimal
    callback_contact: str = ""


class LineItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal


class Invoice(BaseModel):
    source: str
    vendor_name: str | None = None
    registration_no: str | None = None
    invoice_no: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    total: Decimal | None = None
    pay_to: str | None = None
    po_ref: str | None = None  # purchase-order reference printed on the invoice, if any
    total_currency: str | None = None  # currency token found on the total line (e.g. "tUSDC", "Rp")
    notes: str = ""
    line_items: list[LineItem] = Field(default_factory=list)
    raw_text: str = ""
    extractor: str = "deterministic"
    warnings: list[str] = Field(default_factory=list)  # extraction assumptions / unreadable fields


class PurchaseOrder(BaseModel):
    """An open purchase order / expected bill: the business's own record that something was ordered."""

    id: str
    vendor_id: str
    description: str
    amount: Decimal
    invoices_allowed: int = 1  # call-offs a blanket order may be invoiced in
    issued_on: date | None = None
    status: str = "open"  # open | closed


class Obligation(BaseModel):
    id: str
    vendor_id: str
    description: str
    amount: Decimal
    day_of_month: int


class Decision(BaseModel):
    kind: str  # invoice | obligation | treasury | instruction
    subject: str  # human readable subject, e.g. "HX-2026-1042 from Shenzhen Huaxin Packaging"
    action: Action
    vendor_id: str | None = None
    payee: str | None = None
    amount: Decimal | None = None
    ref: str | None = None  # hex bytes32 payment reference
    po_id: str | None = None  # purchase order this payment is matched to (three-way-match stand-in)
    findings: list[Finding] = Field(default_factory=list)
    risk_score: int = 0
    plan: list[str] = Field(default_factory=list)
    explanation: str = ""
    decided_at: int = 0  # chain timestamp
    llm_used: bool = False

    def codes(self) -> list[str]:
        return [f.code for f in self.findings]


class ExecutionResult(BaseModel):
    decision: Decision
    decision_hash: str
    tx_hashes: list[str] = Field(default_factory=list)
    onchain: str = ""  # AutoPaid | ProposalCreated(id) | DecisionCommitted | none
    proposal_id: int | None = None
    error: str | None = None


class Intent(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    source: str = "nlu"  # nlu | llm
