"""Kendali — a policy-bounded AI treasury agent for small businesses.

"Kendali" is Indonesian for *control*. The agent reads invoices and instructions, decides what
to pay, and executes on-chain — but every action passes three independent guardrail layers:

1. an LLM / NLU layer that only *proposes* structured intents (it never sees keys or addresses),
2. a deterministic policy engine that decides (screening, fraud signals, limits, liquidity),
3. the KendaliVault smart contract, which enforces the hard limits on-chain even if
   layers 1 and 2 are fully compromised.
"""

__version__ = "1.0.0"
