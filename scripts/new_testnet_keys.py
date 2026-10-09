"""Create three fresh testnet keys (deployer / owner / agent) in .env. Prints the address to fund.

    python scripts/new_testnet_keys.py --rpc https://ethereum-sepolia-rpc.publicnode.com \
        --explorer https://sepolia.etherscan.io/tx/ --network sepolia

Never reuse these keys on mainnet. .env is git-ignored.
"""

import argparse
from pathlib import Path

from eth_account import Account

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--rpc", required=True)
ap.add_argument("--network", default="sepolia")
ap.add_argument("--explorer", default="https://sepolia.etherscan.io/tx/")
args = ap.parse_args()

env = ROOT / ".env"
if env.exists():
    raise SystemExit(".env already exists; delete it first if you really want new keys")
accts = {name: Account.create() for name in ("DEPLOYER", "OWNER", "AGENT")}
lines = [
    f"KENDALI_NETWORK={args.network}",
    f"KENDALI_RPC_URL={args.rpc}",
    f"KENDALI_EXPLORER_TX_URL={args.explorer}",
] + [f"KENDALI_{n}_KEY={a.key.hex() if a.key.hex().startswith('0x') else '0x' + a.key.hex()}" for n, a in accts.items()]
env.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Wrote .env")
print("Fund this DEPLOYER address with test ETH from a faucet (~0.15 ETH covers everything):")
print("   ", accts["DEPLOYER"].address)
print("Owner:", accts["OWNER"].address, " Agent:", accts["AGENT"].address, "(topped up automatically by the deployer)")
