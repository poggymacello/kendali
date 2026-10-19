"""Runtime configuration (environment variables, optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "contracts" / "out"
DEPLOYMENTS_DIR = ROOT / "deployments"
RUNS_DIR = ROOT / "runs"

# Anvil's well-known development keys. NEVER use them on a public network.
ANVIL_KEYS = [
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",  # deployer
    "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",  # owner (treasurer)
    "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",  # agent (AI hot key)
]
# Local anvil networks always use the anvil keys above, even when a .env with public-testnet keys exists.
LOCAL_NETWORKS = {"devnet", "eval", "pytest"}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    rpc_url: str = field(default_factory=lambda: os.getenv("KENDALI_RPC_URL", "http://127.0.0.1:8545"))
    network: str = field(default_factory=lambda: os.getenv("KENDALI_NETWORK", "devnet"))
    deployer_key: str = field(default_factory=lambda: os.getenv("KENDALI_DEPLOYER_KEY", ANVIL_KEYS[0]))
    owner_key: str = field(default_factory=lambda: os.getenv("KENDALI_OWNER_KEY", ANVIL_KEYS[1]))
    agent_key: str = field(default_factory=lambda: os.getenv("KENDALI_AGENT_KEY", ANVIL_KEYS[2]))
    explorer_tx_url: str = field(default_factory=lambda: os.getenv("KENDALI_EXPLORER_TX_URL", ""))
    # LLM (any OpenAI-compatible endpoint: OpenAI, DeepSeek, Qwen/DashScope, local vLLM/Ollama)
    llm_base_url: str = field(default_factory=lambda: os.getenv("KENDALI_LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("KENDALI_LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("KENDALI_LLM_MODEL", ""))
    data_dir: Path = DATA_DIR
    runs_dir: Path = RUNS_DIR

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_model and (self.llm_api_key or self.llm_base_url))

    def tx_link(self, tx_hash: str) -> str:
        return f"{self.explorer_tx_url}{tx_hash}" if self.explorer_tx_url else tx_hash
