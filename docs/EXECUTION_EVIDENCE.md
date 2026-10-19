# Kendali — Execution Evidence

**Team:** Kendali · Institut Teknologi Bandung (Indonesia) · **Topic F — Agent Wallet**  
**What the rules ask for:** "Execution evidence (… for the on-chain topic: real on-chain transaction hashes)".

This document lists every piece of execution evidence we have, says honestly what kind of chain each one ran on, and explains how a judge can reproduce or verify it.

| # | Evidence | Chain | Status | File |
|---|---|---|---|---|
| E1 | **Public testnet run**: the agent deploys its vault, pays, proposes, gets owner approval, blocks attacks, parks cash in the reserve, and a stolen-key payment **reverts on-chain** | **Ethereum Sepolia** (chain id 11155111), public | **PENDING**: waits for the deployer address to be funded with Sepolia ETH (see §2) | `reports/TESTNET_EVIDENCE.md`, `reports/testnet-evidence.json` |
| E2 | Automated scenario evaluation: 22 tasks + 35 attacks, each on a fresh EVM snapshot, **113 transactions** | private anvil devnet (chain id 31337) | **Done.** Re-run on 19 Oct 2026 after the red-team fixes: **57/57 pass**, task completion 100%, attack prevention 100%, attacker wallets never funded, 23.6 s | `reports/EVAL_REPORT.md`, `reports/eval-results.json` |
| E3 | Dress rehearsal of E1 with the **same keys and the same script** against a local fork of live Sepolia state (Amsterdam rules, real contract sizes and gas) | anvil fork of Sepolia (not public) | **Done** on 19 Oct 2026: all 14 steps succeeded, audit trail `ok=True, anchored 8/8` | this document, §3 |
| E4 | Smart-contract tests: 17 unit/fuzz tests + a stateful invariant suite (4 invariants, 128 runs × 64 calls = 8,192 random calls) | Foundry EVM | **Done.** 19 Oct 2026: **18/18 pass** | `contracts/test/KendaliVault.t.sol` |
| E5 | Python tests incl. an end-to-end on-chain run and the LLM path | anvil devnet | **Done.** 19 Oct 2026: **84/84 pass** | `tests/` |

> Earlier versions of `reports/TESTNET_EVIDENCE.md` came from a **local simulated chain ("testnet-sim", chain id 4242)**. That run is *not* public-chain evidence and is replaced by E1 as soon as the Sepolia run completes.

---

## 1. What the public testnet run proves (E1)

`scripts/testnet_evidence.py` performs these steps on Sepolia. Every row produces a public transaction hash with an Etherscan link in `reports/TESTNET_EVIDENCE.md`.

| Step | What happens | Shows | On-chain artefact |
|---|---|---|---|
| 1–3 | Deploy `MockUSDC` (valueless tUSDC), `ReserveVault` (ERC-4626) and `KendaliVault`; fund the vault with 25,000 tUSDC; the **owner** key onboards six KYB-verified vendors | contract deployment, owner-only governance (T3) | contract creation, `PayeeAdded` |
| — | Wait for the on-chain payee cooling-off period (testnet profile: 180 s of real time) | new beneficiaries cannot be paid at once | `activeFrom` in `PayeeAdded` |
| 4 | Agent pays invoice HX-2026-1042 (540 tUSDC) on its own | autonomous execution within limits (T1) | `AutoPaid` with the decision hash |
| 5–6 | Agent proposes KTG-0915 (2,850 tUSDC, above its 1,000 solo limit); the owner key approves it | maker-checker (T2), segregation of duties | `ProposalCreated`, `ProposalApproved` |
| 7–10 | Agent blocks a business-email-compromise invoice, a prompt-injection invoice, an address-poisoning invoice and a sanctioned counterparty | policy engine stops fraud before signing; refusals are anchored for audit | `DecisionCommitted` |
| 11 | Agent refuses a chat message that impersonates the owner | mandate checks override the LLM | `DecisionCommitted` |
| 12 | Agent keeps a runway and moves idle cash into the ERC-4626 reserve | treasury management | `ReserveDeposited` |
| 13 | A **stolen agent key** signs `pay(attacker, 100)` and broadcasts it | the contract, not the prompt, is the last line of defence | **failed transaction (status 0)**, reason `PayeeNotAllowed(attacker)` |
| 14 | The local hash-chained audit log is verified against the decision hashes found on-chain | tamper-evident, verifiable AI decisions | `ok=True, anchored=N/N` |

**How a judge verifies a hash:** open the link in `reports/TESTNET_EVIDENCE.md` (Sepolia Etherscan) → check *From* (agent or owner address, listed in `deployments/sepolia-11155111.json`), *To* (the vault), *Status*, and the *Logs* tab for the event. The `decisionHash` in each event is the keccak256 of the agent's decision record; step 14 recomputes every record in the run's local hash-chained audit log (`runs/sepolia-…/audit.jsonl`, synthetic data only, available on request) and matches it against these events.

## 2. Status of the public run and how to complete it

* Network: Ethereum Sepolia, RPC `https://ethereum-sepolia-rpc.publicnode.com`, explorer `https://sepolia.etherscan.io/tx/`.
* Fresh keys were generated with `scripts/new_testnet_keys.py` and stored in the git-ignored `.env`. The private keys are never printed, logged or committed.
* **Deployer address to fund: `0x1bD652D9EaF19f2a1869932A374528D3332103f8`** (owner `0x71Fbf13D39DAbA40Fb556461d46aA7B9b3BC650F`, agent `0x208699d2Ab3b0bc821c374186dEfcc97305fc9e2` are topped up automatically by the deployer).
* Budget: **0.05 Sepolia ETH is enough** (measured in the rehearsal, §3); 0.1 ETH leaves a comfortable margin.

```bash
# after the deployer address holds Sepolia ETH:
python scripts/testnet_evidence.py        # about 6 minutes (includes the 180 s cooling-off)
git add reports/TESTNET_EVIDENCE.md reports/testnet-evidence.json deployments/sepolia-11155111.json
git commit -m "Add public Sepolia execution evidence"
```

### Public Sepolia hashes (filled after the run)

<!-- FILL-AFTER-SEPOLIA-RUN: copy from reports/TESTNET_EVIDENCE.md -->
| Item | Value |
|---|---|
| Run date (UTC) | _pending_ |
| KendaliVault address | _pending_ |
| Agent auto-payment (`AutoPaid`) | _pending_ |
| Owner approval (`ProposalApproved`) | _pending_ |
| Blocked BEC invoice (`DecisionCommitted`) | _pending_ |
| Reserve deposit (`ReserveDeposited`) | _pending_ |
| **Stolen-key payment, reverted** | _pending_ |
| Audit verification | _pending_ |

The complete table with every hash is generated automatically in [`reports/TESTNET_EVIDENCE.md`](../reports/TESTNET_EVIDENCE.md).

## 3. Rehearsal on a Sepolia fork (E3)

Before spending any testnet ETH we ran the exact public-run script, with the real keys from `.env`, against `anvil --fork-url https://ethereum-sepolia-rpc.publicnode.com` (chain id 11155111, live Sepolia state, Amsterdam hardfork rules). The deployer was given test balance on the fork only.

* First attempt: **failed** at step 3. The deployer's gas top-up to the owner and agent used a hard-coded 21,000 gas limit. Since the Amsterdam upgrade, a transfer that creates a new account costs far more (Sepolia's own node estimates about 207,000 gas), so the top-up reverted silently and the owner had no gas. A second latent issue: `maxFeePerGas` was set to `2 × gas_price` (≈ 34 wei on Sepolia today), which is below the 1 gwei tip and would have been rejected by a real node.
* Fix (`kendali/deploy.py::_ensure_gas`): estimate the gas, use a generous limit (unused gas is refunded), set `maxFeePerGas = 2 × baseFee + tip`, and stop with a clear error if a top-up fails.
* After the fix: **all 14 steps succeeded**, the stolen-key transaction reverted with `PayeeNotAllowed(attacker)`, and the audit trail verified (`ok=True, anchored=8/8`). A second rehearsal starting from exactly 0.05 ETH also completed all 14 steps (0.0017 ETH left over, with the fork charging about 1 gwei per gas; live Sepolia fees are currently far lower).
* Rehearsal hashes are not listed here on purpose: they exist only on a local fork and cannot be checked on a public explorer.

## 4. Local devnet evaluation (E2) — how to reproduce

```bash
pip install -e ".[dev]"
python eval/run_eval.py     # starts its own anvil devnet; no API key, no real funds
```
Expected summary (19 Oct 2026 run):

```json
{"scenarios": 57, "passed": 57, "task_completion_rate": 1.0, "attack_prevention_rate": 1.0,
 "attacker_funds_safe_in_all_scenarios": true, "transactions_executed": 113}
```

Every scenario's steps, decisions and transaction hashes are in `reports/eval-results.json`. The per-scenario table, with the first transaction of each scenario, is in `reports/EVAL_REPORT.md`.

| Group | Scenarios | Result |
|---|---|---|
| Tasks: invoices EN/ID/PDF, maker-checker, due dates, recurring bills, treasury, chat, audit, emergency pause | T01–T19 | 19/19 PASS |
| Red-team tasks: unusual invoice layout, "urgent shipment" false-positive check, thousands separators | T20–T22 | 3/3 PASS |
| Document attacks: BEC, prompt injection (EN, ID, zero-width), duplicates, homoglyphs, poisoning, unknown issuer, sanctions, inflated amounts, bad arithmetic, hard cap | A01–A09, A14, A15, A23 | 12/12 PASS |
| Chat attacks: owner impersonation, raw address, raise limit, unlimited allowance | A10–A13 | 4/4 PASS |
| Red-team attacks: polite BEC, fake invoice from a real vendor with a paraphrased approval claim, Indonesian-slang claim, split invoices, lower-case duplicate, IDR invoice, chat "add wallet and pay", typo-squat, PO forgery, PO tolerance, mixed-script name, "approve everything pending" | A24–A35 | 12/12 PASS |
| Stolen agent key: pay attacker, above limit, many small payments, self-approval, change limits / add payee, replay | A16–A21 | 6/6 PASS (all reverted on-chain) |
| Audit-log tampering | A22 | detected |

## 5. Test commands and results (19 Oct 2026, Windows 11, Python 3.11.9, Foundry 1.8.5)

| Command | Result |
|---|---|
| `pytest` | 84 passed |
| `cd contracts && forge test` | 18 passed, 0 failed (incl. 4 invariants over 8,192 random calls) |
| `python eval/run_eval.py` | 57/57 scenarios, 113 transactions |
