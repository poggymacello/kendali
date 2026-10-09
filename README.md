# Kendali — a policy-bounded AI treasury agent

> *Kendali* means **control** in Indonesian.
> **The LLM proposes, the policy decides, the contract enforces.**

Kendali is an AI agent that runs the payables and treasury of a small cross-border business. It reads invoices (text, PDF, JSON) and owner instructions (English or Bahasa Indonesia), pays suppliers on-chain, runs recurring obligations and parks idle cash in an ERC-4626 reserve.

It does all of this without being trickable: business-email-compromise, prompt injection, look-alike wallets, sanctioned counterparties and even a **stolen agent key** cannot move funds to an attacker. The hard limits live in a smart contract, not in the prompt.

*FinTechathon 2026 — International Track, Topic F (Agent Wallet).*

![Architecture](docs/img/architecture.png)

## Results at a glance

| | |
|---|---|
| Scenario evaluation (19 tasks + 23 attacks, each on a fresh EVM snapshot) | **42 / 42 pass** · task completion **100%** · attack prevention **100%** |
| Attacker / decoy wallets funded in any scenario | **never** |
| Smart-contract tests (unit + fuzz + stateful invariants, 8,192 random calls/run) | **18 / 18 pass** |
| Python tests (security, extraction EN/ID/PDF, NLU, policy, audit, LLM path, on-chain e2e) | **55 / 55 pass** |
| Worst case with a stolen agent key | pay only allow-listed vendors, ≤ 1,000 per payment, ≤ 2,500 per day |

Reports: [`reports/EVAL_REPORT.md`](reports/EVAL_REPORT.md) · [`docs/TECHNICAL_DOCUMENTATION.md`](docs/TECHNICAL_DOCUMENTATION.md) · [`docs/SECURITY_SELF_ASSESSMENT.md`](docs/SECURITY_SELF_ASSESSMENT.md) · [`docs/EXECUTION_EVIDENCE.md`](docs/EXECUTION_EVIDENCE.md)

## Quick start (≈5 minutes)

**Requirements:** Python 3.10+, [Foundry](https://getfoundry.sh) (for `anvil` and `forge`), Git.

```bash
git clone <repo-url> kendali && cd kendali
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,docs]"

# 1) reproducible evaluation: starts its own devnet, runs 42 scenarios, writes reports/
python eval/run_eval.py

# 2) tests
pytest
cd contracts && forge test && cd ..

# 3) interactive demo
python -m kendali devnet            # terminal 1: local chain + deploy + seed (keep running)
streamlit run app/streamlit_app.py  # terminal 2: open http://localhost:8501
```

If `anvil` is not on your PATH, set `KENDALI_ANVIL=/path/to/anvil`.

### CLI
```bash
python -m kendali status
python -m kendali process                       # whole inbox
python -m kendali process data/invoices/inbox/inv-01-huaxin-HX-2026-1042.txt
python -m kendali chat "tolong bayar semua tagihan yang jatuh tempo minggu ini"
python -m kendali chat "keep 14 days of runway liquid and park the rest"
python -m kendali obligations
python -m kendali approve 0                     # owner console (owner key)
python -m kendali audit-verify
```

### Use a real LLM (optional)
Any OpenAI-compatible endpoint works. Without one, Kendali runs its deterministic extractor and NLU, which is also the reproducible baseline used for grading.
```bash
# OpenAI
export KENDALI_LLM_API_KEY=sk-...   KENDALI_LLM_MODEL=gpt-4.1-mini
# DeepSeek
export KENDALI_LLM_BASE_URL=https://api.deepseek.com  KENDALI_LLM_API_KEY=...  KENDALI_LLM_MODEL=deepseek-chat
# Qwen (DashScope compatible mode)
export KENDALI_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  KENDALI_LLM_API_KEY=...  KENDALI_LLM_MODEL=qwen-plus
python eval/run_eval.py --llm
```

### Public testnet evidence
```bash
python scripts/new_testnet_keys.py --rpc https://ethereum-sepolia-rpc.publicnode.com --network sepolia
# fund the printed deployer address with test ETH, then:
python scripts/testnet_evidence.py   # writes reports/TESTNET_EVIDENCE.md with explorer links
```

## How it works

| Layer | Role | Key properties |
|---|---|---|
| ① Understand | LLM + deterministic extractor/NLU | closed intent set, schema-validated JSON, untrusted documents spotlighted, model never sees keys or chooses payees |
| ② Decide | deterministic policy engine | KYB payee binding, screening, BEC / injection / homoglyph / poisoning / duplicate / anomaly detectors, limits, liquidity, due dates, routing table, **pre-sign simulation** |
| ③ Enforce | `KendaliVault.sol` | allow-list + cooling-off, 1,000 per tx / 2,500 per day, maker-checker up to 10,000, time-locked loosening of policy, circuit breaker, decision hashes anchored in events |

**Permission tiers:**
* **T0** read-only
* **T1** autonomous within on-chain limits
* **T2** maker-checker (the agent proposes, the owner approves)
* **T3** owner-only governance, with time-locked loosening

Details: [security self-assessment](docs/SECURITY_SELF_ASSESSMENT.md).

## Repository
```
contracts/  KendaliVault, ReserveVault (ERC-4626), MockUSDC + Foundry tests; artifacts/ = ABI+bytecode
kendali/    agent package: chain, invoices, llm, nlu, policy, security, registry, treasury, audit, agent, cli
eval/       scenarios.yaml (42 scenarios) + run_eval.py (automated grader)
tests/      pytest suite (55 tests)
app/        Streamlit console (chat, invoices, owner approvals, treasury, audit, guardrails red-team)
data/       synthetic vendor master, screening list, invoice inbox (13 invoices incl. PDF and attacks)
docs/       technical documentation, security self-assessment, execution evidence, diagrams
reports/    evaluation and testnet evidence
scripts/    data generator, diagram renderer, artifact export, testnet keys + evidence
```

## Disclaimer
All companies, people, wallets and the screening list are **synthetic**. `tUSDC` is a valueless test token. The contracts are unaudited; do not use them with real funds.

License: MIT.
