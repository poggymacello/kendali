"""Tamper-evident audit trail.

Every decision is serialised canonically and hashed (keccak256) BEFORE any transaction is
signed; that hash travels inside the transaction (AutoPaid / ProposalCreated /
DecisionCommitted / Reserve* events). Local entries are additionally hash-chained.
`verify()` recomputes everything and cross-checks the chain, so editing or deleting a
local record is detectable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from web3 import Web3

from .models import Action, Decision

GENESIS = "0x" + "00" * 32
ANCHORED_ACTIONS = {Action.EXECUTE, Action.REQUEST_APPROVAL, Action.BLOCK, Action.REFUSE}


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def decision_hash(decision: Decision) -> str:
    return Web3.to_hex(Web3.keccak(text=canonical(decision.model_dump(mode="json"))))


def _entry_hash(prev: str, body: dict) -> str:
    return "0x" + hashlib.sha256((prev + canonical(body)).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append(self, decision: Decision, dhash: str, tx_hashes: list[str], onchain: str,
               proposal_id: int | None, chain_id: int, error: str | None = None) -> dict:
        entries = self.entries()
        prev = entries[-1]["entry_hash"] if entries else GENESIS
        body = {
            "seq": len(entries),
            "chain_id": chain_id,
            "decision": decision.model_dump(mode="json"),
            "decision_hash": dhash,
            "tx_hashes": tx_hashes,
            "onchain": onchain,
            "proposal_id": proposal_id,
            "error": error,
        }
        entry = {**body, "prev_hash": prev, "entry_hash": _entry_hash(prev, body)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical(entry) + "\n")
        return entry

    def verify(self, onchain_hashes: dict[str, str] | None = None) -> dict:
        """Recompute decision hashes and the hash chain; optionally check on-chain anchoring."""
        problems: list[str] = []
        prev = GENESIS
        anchored = 0
        expected = 0
        entries = self.entries()
        for e in entries:
            body = {k: e[k] for k in ("seq", "chain_id", "decision", "decision_hash", "tx_hashes", "onchain", "proposal_id", "error")}
            if e["prev_hash"] != prev:
                problems.append(f"seq {e['seq']}: broken chain link")
            if _entry_hash(e["prev_hash"], body) != e["entry_hash"]:
                problems.append(f"seq {e['seq']}: entry hash mismatch (record edited)")
            recomputed = decision_hash(Decision.model_validate(e["decision"]))
            if recomputed != e["decision_hash"]:
                problems.append(f"seq {e['seq']}: decision content does not match its hash")
            if onchain_hashes is not None and Action(e["decision"]["action"]) in ANCHORED_ACTIONS and not e.get("error"):
                expected += 1
                if e["decision_hash"] in onchain_hashes:
                    anchored += 1
                else:
                    problems.append(f"seq {e['seq']}: decision hash not found on-chain")
            prev = e["entry_hash"]
        return {"entries": len(entries), "anchored": anchored, "expected_anchors": expected, "ok": not problems, "problems": problems}
