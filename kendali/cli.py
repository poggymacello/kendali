"""Command-line interface.

    python -m kendali devnet            # start anvil, deploy, seed (keeps running)
    python -m kendali status
    python -m kendali process [FILE]    # one invoice, or the whole inbox
    python -m kendali chat "bayar semua tagihan yang jatuh tempo minggu ini"
    python -m kendali obligations
    python -m kendali rebalance [--days 14]
    python -m kendali approve ID | reject ID --reason "..."   (owner console)
    python -m kendali audit-verify
    python -m kendali deploy --profile testnet                 (public testnet)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .agent import KendaliAgent, OwnerConsole
from .chain import Chain
from .config import RUNS_DIR, Settings
from .deploy import deploy_all, devnet_settings, seed_devnet, start_anvil
from .llm import get_llm
from .registry import Registry


def _agent(settings: Settings) -> KendaliAgent:
    chain = Chain(settings)
    if chain.vault is None:
        sys.exit("No deployment found for this network. Run `python -m kendali devnet` or `deploy` first.")
    return KendaliAgent(settings, chain, get_llm(settings))


def _print_result(r) -> None:
    print(r.decision.explanation)
    if r.tx_hashes:
        print("tx:", ", ".join(r.tx_hashes))
    if r.error:
        print("error:", r.error)
    print()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="kendali", description="Kendali AI treasury agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("devnet", help="start a local anvil devnet, deploy and seed")
    d.add_argument("--port", type=int, default=8545)
    d.add_argument("--no-wait", action="store_true", help="deploy and exit (anvil keeps running)")
    sub.add_parser("status")
    pr = sub.add_parser("process")
    pr.add_argument("file", nargs="?")
    pr.add_argument("--force", action="store_true", help="pay even if not yet due")
    ch = sub.add_parser("chat")
    ch.add_argument("message")
    sub.add_parser("obligations")
    rb = sub.add_parser("rebalance")
    rb.add_argument("--days", type=int, default=None)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("id", type=int)
    rj = sub.add_parser("reject")
    rj.add_argument("id", type=int)
    rj.add_argument("--reason", default="rejected by owner")
    sub.add_parser("unpause")
    sub.add_parser("audit-verify")
    dp = sub.add_parser("deploy")
    dp.add_argument("--profile", default="testnet", choices=["devnet", "testnet"])
    args = ap.parse_args(argv)

    if args.cmd == "devnet":
        settings = devnet_settings(args.port)
        if RUNS_DIR.exists():
            for old in RUNS_DIR.glob("devnet-31337*"):
                shutil.rmtree(old, ignore_errors=True)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        proc = start_anvil(args.port, log_path=RUNS_DIR / "anvil.log")
        chain = Chain(settings, load=False)
        dep = seed_devnet(chain, Registry.load(settings.data_dir))
        print(json.dumps(dep, indent=2))
        print(f"\nDevnet ready at {settings.rpc_url} (anvil pid {proc.pid}).")
        if args.no_wait:
            return
        print("Press Ctrl+C to stop.")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return

    settings = Settings()
    if args.cmd == "deploy":
        chain = Chain(settings, load=False)
        dep = deploy_all(chain, Registry.load(settings.data_dir), args.profile)
        print(json.dumps(dep, indent=2))
        return

    agent = _agent(settings)
    if args.cmd == "status":
        print(json.dumps(agent.status(), indent=2))
    elif args.cmd == "process":
        if args.file:
            _print_result(agent.process_invoice(Path(args.file), force=args.force))
        else:
            for r in agent.process_inbox():
                _print_result(r)
    elif args.cmd == "chat":
        reply = agent.handle(args.message)
        print(f"[intent: {reply.intent.name} via {reply.intent.source}]")
        print(reply.text)
    elif args.cmd == "obligations":
        for r in agent.run_obligations():
            _print_result(r)
    elif args.cmd == "rebalance":
        _print_result(agent.rebalance(args.days))
    elif args.cmd in ("approve", "reject", "unpause"):
        owner = OwnerConsole(agent.chain, agent.registry)
        if args.cmd == "approve":
            print("approved:", owner.approve(args.id))
        elif args.cmd == "reject":
            print("rejected:", owner.reject(args.id, args.reason))
        else:
            print("unpaused:", owner.unpause())
    elif args.cmd == "audit-verify":
        print(json.dumps(agent.audit.verify(agent.chain.onchain_decision_hashes()), indent=2))


if __name__ == "__main__":
    main()
