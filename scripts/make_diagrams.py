"""Render the architecture and decision-flow diagrams used in the docs and the deck."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#0f172a"
TEAL = "#0f766e"
AMBER = "#b45309"
RED = "#b91c1c"
SLATE = "#475569"
BLUE = "#1d4ed8"


def box(ax, x, y, w, h, title, body, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", linewidth=2,
                                edgecolor=color, facecolor="white"))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.42), w, 0.42, boxstyle="round,pad=0.02,rounding_size=0.06", linewidth=0,
                                facecolor=color))
    ax.text(x + w / 2, y + h - 0.21, title, ha="center", va="center", color="white", fontsize=11, weight="bold")
    ax.text(x + 0.12, y + h - 0.55, body, ha="left", va="top", color=INK, fontsize=8.6, linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, label="", color=INK):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16, linewidth=1.8, color=color))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", va="bottom", fontsize=8, color=color, style="italic")


def architecture():
    fig, ax = plt.subplots(figsize=(14, 6.4), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    box(ax, 0.2, 3.3, 2.6, 2.7, "Untrusted inputs", "• invoices (txt / PDF / JSON)\n• owner chat (EN / ID)\n• recurring obligations\n• treasury policy\n\nTreated as DATA,\nnever as commands", SLATE)
    box(ax, 3.3, 3.3, 3.1, 2.7, "① Understand", "LLM (any OpenAI-compatible:\nOpenAI / DeepSeek / Qwen)\n+ deterministic extractor & NLU\n\n• closed intent set\n• JSON schema validation\n• random-boundary spotlighting\n• no keys, no addresses", BLUE)
    box(ax, 6.9, 3.3, 3.3, 2.7, "② Decide (deterministic)", "• KYB payee binding\n• screening (sanctions/scam)\n• BEC, injection, homoglyph,\n  poisoning, duplicate, anomaly\n• limits + liquidity + due dates\n• routing table → action\n• pre-sign simulation", AMBER)
    box(ax, 10.7, 3.3, 3.1, 2.7, "③ Enforce (on-chain)", "KendaliVault.sol\n• allow-list + cooling-off\n• 1,000 / tx · 2,500 / day\n• maker-checker > 1,000\n• hard cap 10,000\n• time-locked policy changes\n• circuit breaker", TEAL)
    arrow(ax, 2.8, 4.65, 3.3, 4.65, "")
    arrow(ax, 6.4, 4.65, 6.9, 4.65, "")
    arrow(ax, 10.2, 4.65, 10.7, 4.65, "")
    box(ax, 6.9, 0.25, 3.3, 2.45, "Owner console", "separate OWNER key\n• approve / reject proposals\n• onboard payees (KYB)\n• change limits (time-locked)\n• unpause, rotate agent key\n(multisig in production)", RED)
    box(ax, 10.7, 0.25, 3.1, 2.45, "Verifiable audit", "decision record → keccak256\n→ carried inside the tx\n(AutoPaid / ProposalCreated /\nDecisionCommitted / Reserve*)\n+ hash-chained local log\n→ verify() any time", INK)
    box(ax, 3.3, 0.25, 3.1, 2.45, "Treasury", "• runway forecast from\n  obligations + payables\n• sweep idle cash → ERC-4626\n• withdraw before paying\n• funds never leave custody", BLUE)
    arrow(ax, 10.2, 2.2, 10.75, 3.3, "")
    arrow(ax, 12.25, 3.3, 12.25, 2.7, "")
    arrow(ax, 4.85, 2.7, 6.95, 3.35, "")
    ax.text(7.0, 6.25, "Kendali — the LLM proposes, the policy decides, the contract enforces",
            ha="center", va="center", fontsize=14, weight="bold", color=INK)
    fig.savefig(OUT / "architecture.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def routing():
    fig, ax = plt.subplots(figsize=(12, 3.6), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    steps = [
        ("Any CRITICAL finding?", "injection · BEC · poisoning\nhomoglyph · unknown vendor\nsanctions · duplicate · hard cap", "BLOCK\n+ anchor hash", RED),
        ("Paused / not due /\nno funds?", "circuit breaker\npay ≤ 3 days before due\ntreasury cannot cover", "HOLD", SLATE),
        ("HIGH finding or\nabove solo limit?", "anomaly · arithmetic · extractor\ndisagreement · cooling-off\n> 1,000 or daily budget used", "REQUEST_APPROVAL\n(maker-checker)", AMBER),
        ("Otherwise", "all checks passed and\npre-sign simulation OK", "EXECUTE\n(agent pays alone)", TEAL),
    ]
    for i, (q, d, a, c) in enumerate(steps):
        x = 0.2 + i * 2.95
        ax.add_patch(FancyBboxPatch((x, 1.55), 2.6, 1.8, boxstyle="round,pad=0.02,rounding_size=0.08", edgecolor=c, facecolor="white", linewidth=2))
        ax.text(x + 1.3, 3.05, q, ha="center", va="center", fontsize=10, weight="bold", color=INK)
        ax.text(x + 1.3, 2.15, d, ha="center", va="center", fontsize=7.4, color=SLATE, linespacing=1.4)
        ax.add_patch(FancyBboxPatch((x + 0.25, 0.25), 2.1, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08", facecolor=c, edgecolor=c))
        ax.text(x + 1.3, 0.72, a, ha="center", va="center", fontsize=9.5, weight="bold", color="white")
        arrow(ax, x + 1.3, 1.55, x + 1.3, 1.2, "", c)
        ax.text(x + 1.45, 1.36, "yes", fontsize=8, color=c, style="italic", va="center")
        if i < 3:
            arrow(ax, x + 2.6, 2.45, x + 2.95, 2.45, "no")
    fig.savefig(OUT / "routing.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    routing()
    print("diagrams written to", OUT)
