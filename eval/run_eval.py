"""Automated evaluation harness.

Starts a private anvil devnet, deploys and seeds Kendali, then runs every scenario in
eval/scenarios.yaml on a fresh EVM snapshot. Produces:
  reports/eval-results.json   machine-readable results incl. every transaction hash
  reports/EVAL_REPORT.md      human-readable scorecard

Usage:  python eval/run_eval.py [--port 8546] [--only T01,A02] [--llm]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kendali.agent import KendaliAgent, OwnerConsole  # noqa: E402
from kendali.chain import Chain  # noqa: E402
from kendali.config import Settings  # noqa: E402
from kendali.deploy import seed_devnet, start_anvil  # noqa: E402
from kendali.invoices import load_invoice  # noqa: E402
from kendali.llm import get_llm  # noqa: E402
from kendali.money import from_units, to_units  # noqa: E402
from kendali.policy import payment_ref  # noqa: E402
from kendali.registry import Registry  # noqa: E402

INBOX = ROOT / "data" / "invoices" / "inbox"
REPORTS = ROOT / "reports"
TX_RE = re.compile(r"0x[0-9a-fA-F]{64}")


class Ctx:
    def __init__(self, chain: Chain, registry: Registry, settings: Settings, workdir: Path, use_llm: bool):
        self.chain = chain
        self.registry = registry
        self.settings = settings
        self.workdir = workdir
        self.addresses = json.loads((ROOT / "data" / "addresses.json").read_text(encoding="utf-8"))
        self.use_llm = use_llm

    def addr(self, key: str) -> str:
        if key in ("ATTACKER", "POISON"):
            return Web3.to_checksum_address(self.addresses["attacker" if key == "ATTACKER" else "poison_lookalike_of_V002"])
        return self.registry.vendors[key].wallet

    def balance(self, key: str) -> Decimal:
        return from_units(self.chain.usdc.functions.balanceOf(self.addr(key)).call())

    def fill(self, text: str) -> str:
        for k in ["V001", "V002", "V003", "V004", "V005", "V006", "V007"]:
            text = text.replace("{" + k + "}", self.addr(k))
        return text.replace("{ATTACKER}", self.addr("ATTACKER")).replace("{POISON}", self.addr("POISON"))


def set_date(chain: Chain, iso: str) -> None:
    ts = int(datetime.fromisoformat(iso).replace(hour=2, tzinfo=timezone.utc).timestamp())
    if ts > chain.now():
        chain.set_time(ts)


def run_step(ctx: Ctx, agent: KendaliAgent, step: dict, state: dict) -> tuple[bool, list[str], dict]:
    """Execute one step. Returns (passed, failure_messages, record)."""
    c = ctx.chain
    exp = step.get("expect", {}) or {}
    delta_keys = list((exp.get("delta") or {}).keys())
    before = {k: ctx.balance(k) for k in delta_keys}
    rec: dict = {"step": {k: v for k, v in step.items() if k != "expect"}, "tx": []}
    results = []
    reply = None
    revert_name = None
    fails: list[str] = []

    if "set_date" in step:
        set_date(c, step["set_date"])
    elif "invoice" in step or "invoice_text" in step:
        if "drain_liquid_to" in step:
            keep = to_units(Decimal(step["drain_liquid_to"]))
            liquid = c.liquid()
            if liquid > keep:
                c.send(c.owner, c.vault.functions.ownerTransfer(c.owner.address, liquid - keep))
        if "invoice" in step:
            path = INBOX / step["invoice"]
        else:
            path = ctx.workdir / f"inline-{state['n']}.txt"
            state["n"] += 1
            path.write_text(ctx.fill(step["invoice_text"]), encoding="utf-8")
        results = [agent.process_invoice(path, force=step.get("force", False))]
    elif "extract" in step:
        inv = load_invoice(INBOX / step["extract"])
        got = {k: (str(getattr(inv, k)) if getattr(inv, k) is not None else None) for k in exp.get("fields", {})}
        for k, v in exp.get("fields", {}).items():
            if got[k] != str(v):
                fails.append(f"field {k}: expected {v}, got {got[k]}")
        rec["extracted"] = got
    elif "chat" in step:
        reply = agent.handle(ctx.fill(step["chat"]))
        results = reply.results
        rec["intent"] = reply.intent.name
        rec["reply"] = reply.text[:1500]
    elif "obligations" in step:
        results = agent.run_obligations()
    elif "rebalance" in step:
        results = [agent.rebalance((step["rebalance"] or {}).get("days"))]
    elif "owner_approve" in step:
        pid = state.get("last_proposal")
        if pid is None:
            fails.append("no proposal to approve")
        else:
            rec["tx"].append(OwnerConsole(c, ctx.registry).approve(pid))
    elif "owner_unpause" in step:
        rec["tx"].append(OwnerConsole(c, ctx.registry).unpause())
    elif "agent_key_call" in step:
        a = step["agent_key_call"]
        fn_name = a["fn"]
        vf = c.vault.functions
        if fn_name == "pay":
            if "ref_of" in a:
                ref = bytes.fromhex(payment_ref(*a["ref_of"])[2:])
            else:
                ref = Web3.keccak(text=f"attack-{time.time_ns()}")
            fn = vf.pay(ctx.addr(a["to"]), to_units(Decimal(a["amount"])), ref, b"\x00" * 32)
        elif fn_name == "approveProposal":
            fn = vf.approveProposal(int(a["id"]))
        elif fn_name == "scheduleLimits":
            big = to_units(Decimal("1000000"))
            fn = vf.scheduleLimits((big, big, big))
        elif fn_name == "addPayee":
            fn = vf.addPayee(ctx.addr(a["to"]), b"\x00" * 32)
        else:
            raise ValueError(fn_name)
        sim = c.simulate(c.agent, fn)
        revert_name = None if sim.ok else sim.error
        if not sim.ok:
            rec["tx"].append(c.send_expect_revert(c.agent, fn))
        else:
            fails.append(f"agent-key call {fn_name} was NOT rejected")
    elif "agent_key_drain" in step:
        a = step["agent_key_drain"]
        ok_count = 0
        for i in range(int(a["attempts"])):
            fn = c.vault.functions.pay(ctx.addr(a["to"]), to_units(Decimal(a["amount"])), Web3.keccak(text=f"drain-{i}"), b"\x00" * 32)
            sim = c.simulate(c.agent, fn)
            if sim.ok:
                rec["tx"].append(Web3.to_hex(c.send(c.agent, fn)["transactionHash"]))
                ok_count += 1
            else:
                revert_name = sim.error
                rec["tx"].append(c.send_expect_revert(c.agent, fn))
                break
        rec["successful_drain_payments"] = ok_count
    elif "tamper_audit" in step:
        lines = agent.audit.path.read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[-1])
        e["decision"]["amount"] = "54.00"  # pretend we paid less
        lines[-1] = json.dumps(e)
        agent.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif "audit_verify" in step:
        v = agent.audit.verify(c.onchain_decision_hashes())
        rec["audit"] = v
        if "audit_ok" in exp and v["ok"] != exp["audit_ok"]:
            fails.append(f"audit ok expected {exp['audit_ok']}, got {v['ok']} ({v['problems'][:2]})")

    for r in results:
        rec["tx"] += r.tx_hashes
        if r.proposal_id is not None:
            state["last_proposal"] = r.proposal_id
    if results:
        rec["actions"] = [r.decision.action.value for r in results]
        rec["codes"] = [r.decision.codes() for r in results]
        rec["onchain"] = [r.onchain for r in results]
        rec["errors"] = [r.error for r in results if r.error]
        if rec["errors"]:
            fails.append(f"execution errors: {rec['errors']}")

    # ---------------------------------------------------------------- expectations
    if "intent" in exp and (reply is None or reply.intent.name != exp["intent"]):
        fails.append(f"intent expected {exp['intent']}, got {reply.intent.name if reply else None}")
    if "language" in exp and (reply is None or reply.intent.language != exp["language"]):
        fails.append(f"language expected {exp['language']}, got {reply.intent.language if reply else None}")
    if "action" in exp:
        first = results[0].decision.action.value if results else None
        if first != exp["action"]:
            fails.append(f"action expected {exp['action']}, got {first} {results[0].decision.codes() if results else ''}")
    if "codes" in exp and results:
        have = set(results[0].decision.codes())
        missing = [code for code in exp["codes"] if code not in have]
        if missing:
            fails.append(f"missing finding codes {missing}; have {sorted(have)}")
    if "codes_absent" in exp and results:
        have = set(results[0].decision.codes())
        unwanted = [code for code in exp["codes_absent"] if code in have]
        if unwanted:
            fails.append(f"unexpected finding codes {unwanted}; have {sorted(have)}")
    if "onchain" in exp:
        oc = results[0].onchain if results else ""
        if not oc.startswith(exp["onchain"]):
            fails.append(f"onchain expected {exp['onchain']}, got {oc}")
    if "counts" in exp:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.decision.action.value] = counts.get(r.decision.action.value, 0) + 1
        rec["counts"] = counts
        for k, v in exp["counts"].items():
            if counts.get(k, 0) != v:
                fails.append(f"count {k}: expected {v}, got {counts.get(k, 0)}")
    if "revert" in exp and revert_name != exp["revert"]:
        fails.append(f"revert expected {exp['revert']}, got {revert_name}")
    if "paused" in exp and c.paused() != exp["paused"]:
        fails.append(f"paused expected {exp['paused']}, got {c.paused()}")
    if "reserve_min" in exp and from_units(c.reserve_assets()) < Decimal(exp["reserve_min"]):
        fails.append(f"reserve below {exp['reserve_min']}: {from_units(c.reserve_assets())}")
    if "text_contains" in exp and (reply is None or exp["text_contains"] not in reply.text):
        fails.append(f"reply does not contain {exp['text_contains']!r}")
    if exp.get("text_contains_tx") and (reply is None or not TX_RE.search(reply.text)):
        fails.append("reply does not cite a transaction hash")
    for k, v in (exp.get("delta") or {}).items():
        d = ctx.balance(k) - before[k]
        rec.setdefault("deltas", {})[k] = str(d)
        if d != Decimal(v):
            fails.append(f"balance delta {k}: expected {v}, got {d}")
    return (not fails), fails, rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8546)
    ap.add_argument("--only", default="")
    ap.add_argument("--llm", action="store_true", help="use the configured LLM (KENDALI_LLM_*) for cross-checks")
    args = ap.parse_args()

    spec = yaml.safe_load((ROOT / "eval" / "scenarios.yaml").read_text(encoding="utf-8"))
    scenarios = spec["scenarios"]
    if args.only:
        wanted = set(args.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in wanted]

    workdir = Path(tempfile.mkdtemp(prefix="kendali-eval-"))
    proc = start_anvil(args.port, log_path=workdir / "anvil.log")
    try:
        settings = Settings()
        settings.rpc_url = f"http://127.0.0.1:{args.port}"
        settings.network = "eval"
        settings.runs_dir = workdir / "runs"
        chain = Chain(settings, load=False)
        registry = Registry.load(settings.data_dir)
        dep = seed_devnet(chain, registry)
        base = chain.snapshot()
        llm = get_llm(settings) if args.llm else None
        ctx = Ctx(chain, registry, settings, workdir, bool(llm))
        out = []
        t0 = time.time()
        for sc in scenarios:
            chain.revert_to(base)
            base = chain.snapshot()
            chain.set_time(chain.now() + 60)
            agent = KendaliAgent(settings, chain, llm, registry, run_dir=workdir / "runs" / sc["id"])
            state = {"n": 0}
            steps_out, all_fails = [], []
            for i, step in enumerate(sc["steps"]):
                ok, fails, rec = run_step(ctx, agent, step, state)
                rec["passed"] = ok
                steps_out.append(rec)
                all_fails += [f"step {i + 1}: {m}" for m in fails]
            attacker_safe = ctx.balance("ATTACKER") == 0 and ctx.balance("POISON") == 0
            passed = not all_fails and attacker_safe
            out.append({"id": sc["id"], "category": sc["category"], "title": sc["title"], "passed": passed,
                        "attacker_funds_safe": attacker_safe, "failures": all_fails, "steps": steps_out})
            print(f"[{'PASS' if passed else 'FAIL'}] {sc['id']} {sc['title']}" + ("" if passed else f"  -> {all_fails}"))
        elapsed = time.time() - t0
    finally:
        proc.terminate()

    tasks = [r for r in out if r["category"] == "task"]
    attacks = [r for r in out if r["category"] == "attack"]
    txs = sum(len(s["tx"]) for r in out for s in r["steps"])
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_mode": bool(args.llm),
        "scenarios": len(out),
        "passed": sum(r["passed"] for r in out),
        "task_completion_rate": round(sum(r["passed"] for r in tasks) / len(tasks), 4) if tasks else None,
        "attack_prevention_rate": round(sum(r["passed"] for r in attacks) / len(attacks), 4) if attacks else None,
        "attacker_funds_safe_in_all_scenarios": all(r["attacker_funds_safe"] for r in out),
        "transactions_executed": txs,
        "elapsed_seconds": round(elapsed, 1),
        "deployment": {k: dep[k] for k in ("vault", "usdc", "reserve", "owner", "agent")},
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "eval-results.json").write_text(json.dumps({"summary": summary, "results": out}, indent=2), encoding="utf-8")
    write_markdown(summary, out)
    print(json.dumps(summary, indent=2))
    shutil.rmtree(workdir, ignore_errors=True)
    return 0 if summary["passed"] == summary["scenarios"] else 1


def write_markdown(summary: dict, out: list[dict]) -> None:
    lines = [
        "# Kendali — Evaluation Report",
        "",
        f"Generated {summary['generated_at']} on a private anvil devnet (chain id 31337). "
        f"LLM mode: {'on' if summary['llm_mode'] else 'off (deterministic, reproducible)'}.",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Scenarios passed | **{summary['passed']} / {summary['scenarios']}** |",
        f"| Task completion rate (legitimate tasks done correctly) | **{summary['task_completion_rate']:.0%}** |",
        f"| Attack prevention rate (attacks stopped or safely routed) | **{summary['attack_prevention_rate']:.0%}** |",
        f"| Attacker / decoy wallets received funds | **{'never' if summary['attacker_funds_safe_in_all_scenarios'] else 'YES - FAIL'}** |",
        f"| On-chain transactions executed | {summary['transactions_executed']} |",
        f"| Runtime | {summary['elapsed_seconds']} s |",
        "",
        "| ID | Category | Scenario | Result | Outcome | Evidence (first tx) |",
        "|---|---|---|---|---|---|",
    ]
    for r in out:
        outcome = []
        for s in r["steps"]:
            if "actions" in s:
                outcome.append("/".join(s["actions"]) if len(s["actions"]) < 4 else json.dumps(s.get("counts", {})))
            elif "intent" in s:
                outcome.append(s["intent"])
            elif s["step"].get("agent_key_call") or s["step"].get("agent_key_drain"):
                outcome.append("reverted on-chain")
            elif "audit" in s:
                outcome.append("audit ok" if s["audit"]["ok"] else "tamper detected")
        first_tx = next((t for s in r["steps"] for t in s["tx"]), "")
        lines.append(f"| {r['id']} | {r['category']} | {r['title']} | {'PASS' if r['passed'] else 'FAIL'} | "
                     f"{' → '.join(outcome)} | `{first_tx[:18]}…` |" if first_tx else
                     f"| {r['id']} | {r['category']} | {r['title']} | {'PASS' if r['passed'] else 'FAIL'} | "
                     f"{' → '.join(outcome)} | – |")
    lines += ["", "Full step-by-step records, including every transaction hash, are in `reports/eval-results.json`."]
    (REPORTS / "EVAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
