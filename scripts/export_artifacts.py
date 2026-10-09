"""Copy ABI + bytecode from `forge build` output into contracts/artifacts/ so the Python agent
runs without a Solidity toolchain (Foundry is still needed for `anvil`)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contracts" / "out"
DEST = ROOT / "contracts" / "artifacts"

DEST.mkdir(parents=True, exist_ok=True)
for name in ("MockUSDC", "ReserveVault", "KendaliVault"):
    raw = json.loads((OUT / f"{name}.sol" / f"{name}.json").read_text(encoding="utf-8"))
    (DEST / f"{name}.json").write_text(json.dumps({"abi": raw["abi"], "bytecode": raw["bytecode"]["object"]}, indent=1), encoding="utf-8")
    print("exported", name)
