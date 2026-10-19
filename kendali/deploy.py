"""Deployment and local devnet management."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from web3 import Web3

from .chain import Chain
from .config import DEPLOYMENTS_DIR, ROOT, Settings
from .money import to_units
from .registry import Registry

# Demo clock: Sunday 2026-10-11 09:00 WIB. After the payee cooling-off the devnet sits on Monday 12 Oct.
DEVNET_GENESIS = int(datetime(2026, 10, 11, 2, 0, tzinfo=timezone.utc).timestamp())

PARAMS = {
    "devnet": {"autoLimit": "1000", "dailyAutoLimit": "2500", "hardCap": "10000",
               "policyDelay": 2 * 86400, "payeeCooldown": 86400, "proposalTtl": 3 * 86400, "funding": "25000"},
    "testnet": {"autoLimit": "1000", "dailyAutoLimit": "2500", "hardCap": "10000",
                "policyDelay": 600, "payeeCooldown": 180, "proposalTtl": 7 * 86400, "funding": "25000"},
}
INITIAL_PAYEES = ["V001", "V002", "V003", "V004", "V005", "V007"]  # V006 is onboarded later (cooling-off demo)


def find_anvil() -> str:
    candidates = [
        os.getenv("KENDALI_ANVIL", ""),
        shutil.which("anvil") or "",
        str(ROOT.parent / "tools" / "foundry" / "anvil.exe"),
        str(Path.home() / ".foundry" / "bin" / "anvil"),
        str(Path.home() / ".foundry" / "bin" / "anvil.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("anvil not found: install Foundry (https://getfoundry.sh) or set KENDALI_ANVIL")


def start_anvil(port: int = 8545, genesis: int = DEVNET_GENESIS, log_path: Path | None = None) -> subprocess.Popen:
    args = [find_anvil(), "--port", str(port), "--timestamp", str(genesis), "--chain-id", "31337", "--accounts", "10"]
    out = open(log_path, "w") if log_path else subprocess.DEVNULL
    proc = subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT)
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{port}"))
    for _ in range(100):
        try:
            if w3.is_connected():
                return proc
        except Exception:
            pass
        time.sleep(0.1)
    proc.kill()
    raise RuntimeError("anvil did not start")


def deploy_all(chain: Chain, registry: Registry, profile: str = "devnet", payees: list[str] | None = None) -> dict:
    p = PARAMS[profile]
    limits = (to_units(Decimal(p["autoLimit"])), to_units(Decimal(p["dailyAutoLimit"])), to_units(Decimal(p["hardCap"])))
    _ensure_gas(chain)
    usdc, r1 = chain.deploy("MockUSDC", chain.deployer.address)
    reserve, _ = chain.deploy("ReserveVault", usdc.address)
    vault, r3 = chain.deploy("KendaliVault", usdc.address, reserve.address, chain.owner.address, chain.agent.address,
                             limits, p["policyDelay"], p["payeeCooldown"], p["proposalTtl"])
    dep = {
        "network": chain.settings.network,
        "chain_id": chain.chain_id,
        "usdc": usdc.address,
        "reserve": reserve.address,
        "vault": vault.address,
        "owner": chain.owner.address,
        "agent": chain.agent.address,
        "deployer": chain.deployer.address,
        "block": int(r1["blockNumber"]),
        "deploy_txs": {"vault": Web3.to_hex(r3["transactionHash"])},
        "params": p,
        "deployed_at": chain.now(),
    }
    chain.deployment = dep
    chain._bind(dep)
    mint = chain.send(chain.deployer, usdc.functions.mint(vault.address, to_units(Decimal(p["funding"]))))
    dep["deploy_txs"]["fund"] = Web3.to_hex(mint["transactionHash"])
    dep["payee_txs"] = {}
    for vid in payees if payees is not None else INITIAL_PAYEES:
        v = registry.vendors[vid]
        r = chain.send(chain.owner, chain.vault.functions.addPayee(v.wallet, registry.kyb_hash(v)))
        dep["payee_txs"][vid] = Web3.to_hex(r["transactionHash"])
    DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    chain.deployment_path().write_text(json.dumps(dep, indent=2), encoding="utf-8")
    return dep


def _ensure_gas(chain: Chain, min_eth: float = 0.01) -> None:
    """On public testnets the deployer tops up the owner and agent accounts with gas."""
    if chain.chain_id == 31337:
        return
    w3 = chain.w3
    for acct in (chain.owner, chain.agent):
        bal = w3.eth.get_balance(acct.address)
        if bal < w3.to_wei(min_eth, "ether"):
            value = w3.to_wei(min_eth, "ether") - bal
            # Do not hard-code 21,000 gas: since the Amsterdam upgrade, a transfer that creates a new
            # account costs far more (Sepolia estimates ~207k), and some nodes (anvil forks) under-estimate
            # it. Unused gas is refunded, so a generous limit is free.
            try:
                est = w3.eth.estimate_gas({"from": chain.deployer.address, "to": acct.address, "value": value})
            except Exception:  # noqa: BLE001 - fall back to the floor below
                est = 0
            base = w3.eth.get_block("latest").get("baseFeePerGas", 0) or 0
            tip = w3.to_wei(1, "gwei")
            tx = {
                "to": acct.address,
                "value": value,
                "nonce": w3.eth.get_transaction_count(chain.deployer.address, "pending"),
                "chainId": chain.chain_id,
                "gas": max(int(est * 1.5), 400_000),
                # maxFee must cover base fee + tip (gas_price * 2 can be below a 1 gwei tip on Sepolia)
                "maxFeePerGas": base * 2 + tip,
                "maxPriorityFeePerGas": tip,
            }
            signed = chain.deployer.sign_transaction(tx)
            receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction), timeout=300)
            if receipt["status"] != 1:
                raise RuntimeError(f"gas top-up to {acct.address} failed (tx {Web3.to_hex(receipt['transactionHash'])})")


def seed_devnet(chain: Chain, registry: Registry) -> dict:
    """Deploy, pass the initial cooling-off, then onboard V006 (still cooling off on demo day)."""
    dep = deploy_all(chain, registry, "devnet")
    chain.increase_time(PARAMS["devnet"]["payeeCooldown"] + 1)
    v = registry.vendors["V006"]
    r = chain.send(chain.owner, chain.vault.functions.addPayee(v.wallet, registry.kyb_hash(v)))
    dep["payee_txs"]["V006"] = Web3.to_hex(r["transactionHash"])
    chain.deployment_path().write_text(json.dumps(dep, indent=2), encoding="utf-8")
    return dep


def devnet_settings(port: int = 8545) -> Settings:
    s = Settings()
    s.rpc_url = f"http://127.0.0.1:{port}"
    s.network = "devnet"
    return s
