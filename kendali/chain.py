"""Thin, explicit web3 layer: deployment, simulation-before-signing, execution and event reads."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_abi import decode as abi_decode
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.exceptions import ContractCustomError, ContractLogicError

from .config import ANVIL_KEYS, ARTIFACTS_DIR, DEPLOYMENTS_DIR, LOCAL_NETWORKS, ROOT, Settings

COMMITTED_ARTIFACTS = ROOT / "contracts" / "artifacts"


class TxReverted(Exception):
    def __init__(self, tx_hash: str, error: str):
        super().__init__(f"tx {tx_hash} reverted: {error}")
        self.tx_hash = tx_hash
        self.error = error


@dataclass
class SimResult:
    ok: bool
    error: str = ""
    args: tuple = ()
    return_value: Any = None

    def describe(self) -> str:
        if self.ok:
            return "ok"
        return f"{self.error}{self.args}" if self.args else self.error


def load_artifact(name: str) -> dict:
    """Load ABI + bytecode from `forge build` output, or the committed copy in contracts/artifacts."""
    built = ARTIFACTS_DIR / f"{name}.sol" / f"{name}.json"
    committed = COMMITTED_ARTIFACTS / f"{name}.json"
    path = built if built.exists() else committed
    if not path.exists():
        raise FileNotFoundError(f"artifact for {name} not found; run `forge build` in contracts/")
    raw = json.loads(path.read_text(encoding="utf-8"))
    bytecode = raw["bytecode"]["object"] if isinstance(raw.get("bytecode"), dict) else raw["bytecode"]
    return {"abi": raw["abi"], "bytecode": bytecode}


def bytes32_from_text(text: str) -> bytes:
    return Web3.keccak(text=text)


def to_hex(b: bytes) -> str:
    return Web3.to_hex(b)


class Chain:
    def __init__(self, settings: Settings, deployment: dict | None = None, load: bool = True):
        self.settings = settings
        self.w3 = Web3(Web3.HTTPProvider(settings.rpc_url, request_kwargs={"timeout": 60}))
        keys = (settings.deployer_key, settings.owner_key, settings.agent_key)
        if settings.network in LOCAL_NETWORKS:
            # never sign local devnet transactions with (or leak) public-testnet keys from .env
            keys = tuple(ANVIL_KEYS)
        self.deployer: LocalAccount = Account.from_key(keys[0])
        self.owner: LocalAccount = Account.from_key(keys[1])
        self.agent: LocalAccount = Account.from_key(keys[2])
        self._chain_id: int | None = None
        self.artifacts = {n: load_artifact(n) for n in ("MockUSDC", "ReserveVault", "KendaliVault")}
        self._errors = self._build_error_map()
        self.deployment = deployment if deployment is not None else (self.load_deployment() if load else None)
        self.usdc = self.reserve = self.vault = None
        if self.deployment:
            self._bind(self.deployment)

    # ------------------------------------------------------------------ basics
    @property
    def chain_id(self) -> int:
        if self._chain_id is None:
            self._chain_id = self.w3.eth.chain_id
        return self._chain_id

    def is_connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def now(self) -> int:
        return int(self.w3.eth.get_block("latest")["timestamp"])

    def block_number(self) -> int:
        return int(self.w3.eth.block_number)

    def deployment_path(self) -> Path:
        return DEPLOYMENTS_DIR / f"{self.settings.network}-{self.chain_id}.json"

    def load_deployment(self) -> dict | None:
        try:
            p = self.deployment_path()
        except Exception:
            return None
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def _bind(self, dep: dict) -> None:
        self.usdc = self.w3.eth.contract(address=dep["usdc"], abi=self.artifacts["MockUSDC"]["abi"])
        self.reserve = self.w3.eth.contract(address=dep["reserve"], abi=self.artifacts["ReserveVault"]["abi"])
        self.vault = self.w3.eth.contract(address=dep["vault"], abi=self.artifacts["KendaliVault"]["abi"])

    # ------------------------------------------------------------------ errors
    def _build_error_map(self) -> dict[str, tuple[str, list[str]]]:
        out: dict[str, tuple[str, list[str]]] = {}
        for art in self.artifacts.values():
            for item in art["abi"]:
                if item.get("type") != "error":
                    continue
                types = [i["type"] for i in item.get("inputs", [])]
                sig = f"{item['name']}({','.join(types)})"
                sel = Web3.to_hex(Web3.keccak(text=sig)[:4])
                out[sel] = (item["name"], types)
        return out

    def decode_revert(self, data: Any) -> tuple[str, tuple]:
        if isinstance(data, (bytes, bytearray)):
            data = Web3.to_hex(data)
        if not isinstance(data, str) or len(data) < 10:
            return ("Reverted", ())
        sel = data[:10].lower()
        if sel in self._errors:
            name, types = self._errors[sel]
            try:
                args = abi_decode(types, bytes.fromhex(data[10:])) if types else ()
            except Exception:
                args = ()
            return name, tuple(Web3.to_hex(a) if isinstance(a, (bytes, bytearray)) else a for a in args)
        return ("Reverted", (data,))

    def _error_from_exc(self, e: Exception) -> tuple[str, tuple]:
        data = getattr(e, "data", None)
        if isinstance(e, ContractCustomError) and data:
            return self.decode_revert(data)
        if data and isinstance(data, str) and data.startswith("0x"):
            return self.decode_revert(data)
        msg = str(e)
        return (msg.split(":")[-1].strip() or "Reverted", ())

    # ------------------------------------------------------------------ tx helpers
    def simulate(self, account: LocalAccount, fn) -> SimResult:
        """Dry-run the exact call the agent is about to sign (pre-sign simulation)."""
        try:
            rv = fn.call({"from": account.address})
            return SimResult(ok=True, return_value=rv)
        except (ContractCustomError, ContractLogicError) as e:
            name, args = self._error_from_exc(e)
            return SimResult(ok=False, error=name, args=args)

    def send(self, account: LocalAccount, fn, gas: int | None = None):
        params: dict[str, Any] = {
            "from": account.address,
            "nonce": self.w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": self.chain_id,
        }
        if gas:
            params["gas"] = gas
        try:
            tx = fn.build_transaction(params)
        except (ContractCustomError, ContractLogicError) as e:
            name, args = self._error_from_exc(e)
            raise TxReverted("(not sent: estimate failed)", f"{name}{args}") from e
        signed = account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=300)
        if receipt["status"] != 1:
            raise TxReverted(Web3.to_hex(h), "status=0")
        return receipt

    def send_expect_revert(self, account: LocalAccount, fn, gas: int = 300_000) -> str:
        """Broadcast a call that the contract must reject (used to evidence on-chain enforcement)."""
        params = {
            "from": account.address,
            "nonce": self.w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": self.chain_id,
            "gas": gas,
        }
        latest = self.w3.eth.get_block("latest")
        base = latest.get("baseFeePerGas", 0) or 0
        tip = self.w3.to_wei(1, "gwei")
        params["maxPriorityFeePerGas"] = tip
        params["maxFeePerGas"] = base * 2 + tip
        tx = fn.build_transaction(params)
        signed = account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=300)
        if receipt["status"] == 1:
            raise AssertionError("expected a revert but the transaction succeeded")
        return Web3.to_hex(h)

    def deploy(self, name: str, *args):
        art = self.artifacts[name]
        c = self.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
        receipt = self.send(self.deployer, c.constructor(*args))
        return self.w3.eth.contract(address=receipt["contractAddress"], abi=art["abi"]), receipt

    # ------------------------------------------------------------------ dev-chain helpers (anvil)
    def rpc(self, method: str, params: list | None = None) -> Any:
        resp = self.w3.provider.make_request(method, params or [])
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp.get("result")

    def increase_time(self, seconds: int) -> None:
        self.rpc("evm_increaseTime", [int(seconds)])
        self.rpc("evm_mine", [])

    def set_time(self, timestamp: int) -> None:
        self.rpc("evm_setNextBlockTimestamp", [int(timestamp)])
        self.rpc("evm_mine", [])

    def snapshot(self) -> str:
        return self.rpc("evm_snapshot", [])

    def revert_to(self, snap_id: str) -> None:
        self.rpc("evm_revert", [snap_id])

    # ------------------------------------------------------------------ reads
    def limits(self) -> dict:
        a, d, h = self.vault.functions.limits().call()
        return {"autoLimit": a, "dailyAutoLimit": d, "hardCap": h}

    def remaining_daily(self) -> int:
        return self.vault.functions.remainingDailyAuto().call()

    def liquid(self) -> int:
        return self.vault.functions.liquidBalance().call()

    def reserve_assets(self) -> int:
        return self.vault.functions.reserveBalance().call()

    def paused(self) -> bool:
        return self.vault.functions.paused().call()

    def payee(self, addr: str) -> dict:
        allowed, active_from, meta = self.vault.functions.payees(Web3.to_checksum_address(addr)).call()
        return {"allowed": allowed, "activeFrom": active_from, "metaHash": Web3.to_hex(meta)}

    def ref_used(self, ref_hex: str) -> bool:
        return self.vault.functions.usedRef(bytes.fromhex(ref_hex[2:])).call()

    def proposals(self) -> list[dict]:
        n = self.vault.functions.proposalCount().call()
        out = []
        for i in range(n):
            to, amount, created, status, ref, dh = self.vault.functions.getProposal(i).call()
            out.append(
                {
                    "id": i,
                    "to": to,
                    "amount": amount,
                    "createdAt": created,
                    "status": ["None", "Pending", "Executed", "Rejected", "Expired"][status],
                    "ref": Web3.to_hex(ref),
                    "decisionHash": Web3.to_hex(dh),
                }
            )
        return out

    def onchain_decision_hashes(self) -> dict[str, str]:
        """Map decisionHash -> event name for every vault event that anchors a decision."""
        start = int(self.deployment.get("block", 0)) if self.deployment else 0
        found: dict[str, str] = {}
        for ev_name in ("AutoPaid", "ProposalCreated", "DecisionCommitted", "ReserveDeposited", "ReserveWithdrawn"):
            ev = getattr(self.vault.events, ev_name)()
            for log in ev.get_logs(from_block=start):
                dh = log["args"].get("decisionHash")
                if dh is not None:
                    found[Web3.to_hex(dh)] = ev_name
        return found

    def wait_until(self, timestamp: int, poll: float = 5.0) -> None:
        """On public testnets time cannot be warped: wait for real time to pass."""
        while self.now() < timestamp:
            time.sleep(poll)
