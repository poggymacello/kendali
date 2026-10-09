import json
from decimal import Decimal

from kendali.audit import AuditLog, decision_hash
from kendali.models import Action, Decision


def make(i):
    return Decision(kind="invoice", subject=f"INV-{i}", action=Action.EXECUTE, amount=Decimal("10.00"), decided_at=i)


def test_chain_verifies_and_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    hashes = {}
    for i in range(3):
        d = make(i)
        h = decision_hash(d)
        hashes[h] = "AutoPaid"
        log.append(d, h, [f"0x{i:064x}"], "AutoPaid", None, 31337)
    assert log.verify(hashes)["ok"]

    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    e = json.loads(lines[1])
    e["decision"]["amount"] = "1.00"
    lines[1] = json.dumps(e)
    (tmp_path / "audit.jsonl").write_text("\n".join(lines) + "\n")
    report = log.verify(hashes)
    assert not report["ok"] and any("seq 1" in p for p in report["problems"])


def test_missing_onchain_anchor_detected(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    d = make(1)
    log.append(d, decision_hash(d), ["0x1"], "AutoPaid", None, 31337)
    assert not log.verify({})["ok"]


def test_deleting_a_record_breaks_the_chain(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    hashes = {}
    for i in range(3):
        d = make(i)
        hashes[decision_hash(d)] = "AutoPaid"
        log.append(d, decision_hash(d), [], "AutoPaid", None, 31337)
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    del lines[1]
    (tmp_path / "audit.jsonl").write_text("\n".join(lines) + "\n")
    assert not log.verify(hashes)["ok"]
