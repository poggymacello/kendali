"""Generate the SVG diagrams used by the technical documentation (context, deployment, sequences).

    python scripts/docs/make_doc_diagrams.py      # writes docs/img/*.svg

Plain SVG, no dependencies. Colours: accent #0f5c4c (Kendali), slate (external), red (attacker / rejection).
"""

from __future__ import annotations

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "img"
ACCENT, ACCENT_L = "#0f5c4c", "#e3f0ec"
SLATE, SLATE_L = "#475569", "#f1f5f9"
RED, RED_L = "#b91c1c", "#fdecec"
AMBER, AMBER_L = "#9a5b0b", "#fdf3e1"
INK, MUTED = "#1b2430", "#5b6675"
FONT = "Segoe UI, Helvetica Neue, Arial, sans-serif"


def svg(w: int, h: int, body: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{FONT}">\n<defs>'
            f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
            f'<marker id="r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker>'
            f'<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker></defs>\n'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>\n' + "\n".join(body) + "\n</svg>\n")


def text(x, y, s, size=13, weight="normal", fill=INK, anchor="middle", halo=False):
    h = ' stroke="#ffffff" stroke-width="5" stroke-linejoin="round" paint-order="stroke"' if halo else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{h}>'
            f'{escape(s)}</text>')


def box(x, y, w, h, title, lines=(), stroke=ACCENT, fill=ACCENT_L, title_size=14, line_size=12):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
           text(x + w / 2, y + 22, title, title_size, "bold", stroke)]
    for i, ln in enumerate(lines):
        out.append(text(x + w / 2, y + 42 + i * (line_size + 5), ln, line_size, fill=INK))
    return out


def arrow(x1, y1, x2, y2, label="", color=INK, marker="a", dashed=False, lx=None, ly=None, size=11.5):
    dash = ' stroke-dasharray="6,4"' if dashed else ""
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8"{dash} marker-end="url(#{marker})"/>']
    if label:
        out.append(text(lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2 - 6, label, size,
                        fill=color if color != INK else MUTED, halo=True))
    return out


# --------------------------------------------------------------------------- context view
def context() -> str:
    b: list[str] = []
    b += [text(480, 28, "System context: who and what Kendali talks to", 17, "bold", INK)]
    b += box(355, 190, 250, 120, "Kendali agent + vault", ["reads documents and chat,", "decides with a fixed policy,",
                                                            "pays through KendaliVault"])
    b += box(30, 60, 220, 80, "Business owner (treasurer)", ["chat EN/ID · owner console", "holds the OWNER key"], AMBER, AMBER_L)
    b += box(30, 210, 220, 80, "Suppliers", ["send invoices (txt / PDF / JSON)", "receive tUSDC at KYB wallet"], SLATE, SLATE_L)
    b += box(30, 360, 220, 80, "Fraudster / attacker", ["forged invoices, injection,", "stolen agent key"], RED, RED_L)
    b += box(710, 60, 220, 80, "LLM endpoint (optional)", ["any OpenAI-compatible API", "JSON only, no keys, no tools"], SLATE, SLATE_L)
    b += box(710, 210, 220, 80, "EVM chain", ["anvil devnet · Sepolia", "(production: permissioned EVM)"], SLATE, SLATE_L)
    b += box(710, 360, 220, 80, "Reference data", ["vendor master (KYB) · open POs", "screening list · obligations"], SLATE, SLATE_L)
    b += arrow(250, 100, 355, 210, "instructions, approvals", lx=305, ly=140)
    b += arrow(250, 250, 355, 250, "invoices", lx=302, ly=243)
    b += arrow(250, 400, 355, 290, "hostile input", RED, "r", lx=300, ly=372)
    b += arrow(605, 215, 710, 110, "untrusted text → JSON", lx=660, ly=150)
    b += arrow(605, 250, 710, 250, "signed tx, eth_call", lx=657, ly=243)
    b += arrow(710, 400, 605, 290, "read-only", lx=665, ly=372)
    b += [text(480, 470, "Trust boundary: everything entering Kendali from the left and the LLM's output is treated as data, never as a command.",
               12, fill=MUTED)]
    return svg(960, 490, b)


# --------------------------------------------------------------------------- deployment view
def deployment() -> str:
    b: list[str] = []
    b += [text(490, 28, "Deployment view: three environments, same code and contracts", 17, "bold", INK)]
    cols = [
        ("Local devnet (evaluation)", 20, ["tested on Windows 11", "Python 3.11 · Foundry 1.8.5",
                                           "anvil, chain id 31337,", "fixed clock 2026-10-11 02:00 UTC",
                                           "anvil dev keys (public, valueless)", "cooling-off 1 day, timelock 2 days",
                                           "Streamlit console on :8501", "eval: fresh EVM snapshot per scenario"], ACCENT, ACCENT_L),
        ("Public testnet (evidence)", 340, ["Ethereum Sepolia, chain id 11155111", "RPC: publicnode.com (HTTPS)",
                                             "keys generated locally,", "stored in git-ignored .env.sepolia",
                                             "cooling-off 180 s, timelock 600 s", "proposal TTL 7 days",
                                             "tUSDC = valueless MockUSDC", "run: scripts/testnet_evidence.py"], SLATE, SLATE_L),
        ("Production path (not built)", 660, ["permissioned EVM chain", "(e.g. FISCO BCOS; port untested)",
                                              "owner = multisig / custodian", "agent key in HSM / cloud KMS",
                                              "ERP sync for vendors + POs", "licensed settlement asset",
                                              "(tokenized deposit, e-CNY-style)", "real screening feeds"], AMBER, AMBER_L),
    ]
    for title, x, lines, s, f in cols:
        b += box(x, 50, 300, 200, title, lines, s, f, 14, 12)
    b += [f'<rect x="20" y="268" width="940" height="92" rx="8" fill="#ffffff" stroke="{ACCENT}" stroke-width="1.5" stroke-dasharray="5,4"/>',
          text(490, 290, "Same artefacts in every environment", 13.5, "bold", ACCENT),
          text(490, 312, "contracts/src (Solidity 0.8.24, Cancun) · kendali/ Python package · data/ reference files · eval/scenarios.yaml", 12),
          text(490, 332, "Only the RPC URL, the three keys and the deployment profile (devnet | testnet) change; see kendali/deploy.py::PARAMS.", 12, fill=MUTED),
          text(490, 350, "The LLM endpoint is optional in all three; without it the deterministic extractor and NLU are used.", 12, fill=MUTED)]
    return svg(980, 372, b)


# --------------------------------------------------------------------------- sequence diagrams
def sequence(title: str, parts: list[tuple[str, str]], msgs: list[tuple], height_per=36, width=980, foot: str = "") -> str:
    n = len(parts)
    left, right = 95, width - 95
    xs = [left + i * (right - left) / (n - 1) for i in range(n)]
    top = 52
    h = top + 50 + height_per * len(msgs) + (40 if foot else 20)
    b: list[str] = [text(width / 2, 26, title, 16, "bold", INK)]
    colors = {"agent": ACCENT, "owner": AMBER, "ext": SLATE, "attacker": RED, "chain": ACCENT}
    for (name, kind), x in zip(parts, xs):
        c = colors[kind]
        fill = {ACCENT: ACCENT_L, AMBER: AMBER_L, SLATE: SLATE_L, RED: RED_L}[c]
        b.append(f'<rect x="{x - 72}" y="{top}" width="144" height="32" rx="6" fill="{fill}" stroke="{c}" stroke-width="1.8"/>')
        b.append(text(x, top + 21, name, 13.5, "bold", c))
        b.append(f'<line x1="{x}" y1="{top + 32}" x2="{x}" y2="{h - (34 if foot else 14)}" stroke="#cbd5e1" stroke-width="1.4" stroke-dasharray="4,4"/>')
    y = top + 62
    for m in msgs:
        kind = m[0]
        if kind == "note":
            _, i, j, label = m
            need = len(label) * 7.2 + 24
            cx = (xs[i] + xs[j]) / 2
            half = max((max(xs[i], xs[j]) - min(xs[i], xs[j])) / 2 + 60, need / 2)
            cx = min(max(cx, half + 6), width - half - 6)
            x1, x2 = cx - half, cx + half
            b.append(f'<rect x="{x1}" y="{y - 16}" width="{x2 - x1}" height="24" rx="4" fill="#fffbea" stroke="#e5c76b"/>')
            b.append(text((x1 + x2) / 2, y + 1, label, 13, fill=INK))
        elif kind == "self":
            _, i, label = m[:3]
            col = m[3] if len(m) > 3 else INK
            x = xs[i]
            b.append(f'<path d="M{x},{y - 8} h34 v16 h-30" fill="none" stroke="{col}" stroke-width="1.6" marker-end="url(#{"r" if col == RED else "a"})"/>')
            b.append(text(x + 42, y + 4, label, 13, fill=col, anchor="start", halo=True))
        else:
            _, i, j, label = m[:4]
            style = m[4] if len(m) > 4 else ""
            col = RED if "fail" in style else (ACCENT if "ok" in style else INK)
            mk = "r" if col == RED else ("g" if col == ACCENT else "a")
            x1, x2 = xs[i], xs[j]
            x2a = x2 - 4 if x2 > x1 else x2 + 4
            dash = ' stroke-dasharray="6,4"' if "ret" in style else ""
            b.append(f'<line x1="{x1}" y1="{y}" x2="{x2a}" y2="{y}" stroke="{col}" stroke-width="1.7"{dash} marker-end="url(#{mk})"/>')
            b.append(text((x1 + x2) / 2, y - 6, label, 13, fill=col, halo=True))
        y += height_per
    if foot:
        b.append(text(width / 2, h - 12, foot, 12.5, fill=MUTED))
    return svg(width, h, b)


def seq_pay() -> str:
    P = [("Supplier invoice", "ext"), ("Extractor + LLM", "agent"), ("Policy engine", "agent"),
         ("Audit log", "agent"), ("KendaliVault", "chain")]
    M = [("msg", 0, 1, "invoice text (untrusted data)"),
         ("self", 1, "deterministic fields; optional LLM JSON"),
         ("msg", 1, 2, "Invoice + cross-check diffs + injection flag"),
         ("msg", 2, 4, "read limits, daily budget, payee, usedRef", "ret"),
         ("self", 2, "detectors · payee binding · PO match · limits"),
         ("note", 2, 2, "route() → EXECUTE (no CRITICAL/HIGH, ≤ 1,000, budget left)"),
         ("msg", 2, 3, "decision_hash = keccak256(canonical(decision))"),
         ("msg", 2, 4, "eth_call pay(to, amount, ref, hash)  [simulation]", "ret"),
         ("msg", 2, 4, "pay(...) signed by AGENT key", "ok"),
         ("msg", 4, 2, "AutoPaid(to, amount, ref, decisionHash)", "ret ok"),
         ("msg", 2, 3, "append entry (prev_hash ‖ entry → sha256)")]
    return sequence("Runtime view (a): agent pays an invoice inside its limits", P, M,
                    foot="Sepolia: tx 0x3f1fd6ba… (HX-2026-1042, 540 tUSDC), block 11951780. Eval: T01, T06, T20, T21.")


def seq_maker_checker() -> str:
    P = [("Agent", "agent"), ("KendaliVault", "chain"), ("Owner console", "owner"), ("Supplier wallet", "ext")]
    M = [("self", 0, "route() → REQUEST_APPROVAL (2,850 > 1,000 solo limit)"),
         ("msg", 0, 1, "eth_call propose(...)  [simulation]", "ret"),
         ("msg", 0, 1, "propose(to, 2,850, ref, hash) — AGENT key"),
         ("msg", 1, 0, "ProposalCreated(id 0); ref marked used", "ret"),
         ("msg", 1, 2, "pending proposal shown with reasons (EN/ID)", "ret"),
         ("note", 2, 2, "human checks invoice, PO, vendor"),
         ("msg", 2, 1, "approveProposal(0) — OWNER key", "ok"),
         ("self", 1, "checks: Pending, TTL, payee allowed, ≤ hardCap"),
         ("msg", 1, 3, "safeTransfer 2,850 tUSDC", "ok"),
         ("msg", 1, 2, "ProposalApproved(id, approver, to, amount, hash)", "ret ok")]
    return sequence("Runtime view (b): maker-checker approval", P, M,
                    foot="Sepolia: propose 0x69245532…, approve 0xb4f7e639… (blocks 11951781–82). Eval: T02, T04, T09, T22.")


def seq_bec() -> str:
    P = [("Fraudster email", "attacker"), ("Extractor", "agent"), ("Policy engine", "agent"),
         ("Vendor master", "ext"), ("KendaliVault", "chain")]
    M = [("msg", 0, 1, "invoice: 'our wallet changed, pay urgently' + new 0x…", "fail"),
         ("msg", 1, 2, "Invoice(pay_to = 0xcD20…E249)"),
         ("msg", 2, 3, "resolve vendor → KYB wallet", "ret"),
         ("self", 2, "pay_to ≠ KYB wallet → PAYMENT_DETAILS_CHANGED (CRITICAL)", RED),
         ("self", 2, "pressure language → SOCIAL_ENGINEERING_PRESSURE"),
         ("note", 2, 2, "route() → BLOCK; call-back via contact on file"),
         ("msg", 2, 4, "commitDecision(hash, Blocked) — no funds move", "ok"),
         ("msg", 4, 2, "DecisionCommitted(hash, 0)", "ret ok")]
    return sequence("Runtime view (c): business-email-compromise invoice is blocked", P, M,
                    foot="Sepolia: 0x3d8df640… (block 11951783). Eval: A01, A24; poisoning A05, homoglyph A04, A31, A34.")


def seq_stolen_key() -> str:
    P = [("Attacker: stolen key", "attacker"), ("KendaliVault", "chain"), ("Owner", "owner")]
    M = [("note", 0, 0, "bypasses LLM, policy and simulation entirely"),
         ("msg", 0, 1, "pay(attacker, 100 tUSDC, ref, 0x0) signed with AGENT key", "fail"),
         ("self", 1, "onlyAgent ✓  whenNotPaused ✓  payees[attacker].allowed ✗"),
         ("msg", 1, 0, "revert PayeeNotAllowed(attacker) — status 0, no transfer", "ret fail"),
         ("msg", 0, 1, "pay(V002, 5,000) / 5 × 999 / approveProposal / addPayee / reused ref", "fail"),
         ("msg", 1, 0, "ExceedsAutoLimit / ExceedsDailyLimit / NotOwner / RefAlreadyUsed", "ret fail"),
         ("msg", 2, 1, "pause() or setAgent(newKey) — immediate", "ok")]
    return sequence("Runtime view (d): stolen agent key tries to drain the vault", P, M, width=900,
                    foot="Sepolia: 0x433d65fd… status 0 (block 11951790). Eval: A16–A21. Foundry invariants: attacker balance stays 0.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("context", context), ("deployment", deployment), ("seq-pay", seq_pay),
                     ("seq-maker-checker", seq_maker_checker), ("seq-bec", seq_bec), ("seq-stolen-key", seq_stolen_key)]:
        (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print("wrote", OUT / f"{name}.svg")


if __name__ == "__main__":
    main()
