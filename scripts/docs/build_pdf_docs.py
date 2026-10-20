"""Build the judge-facing PDF documents from the Markdown sources.

Each PDF gets a cover page, a document-control table, a table of contents, numbered
headings, running header/footer and page numbers. Markdown -> HTML happens here (Python
`markdown`); HTML -> PDF is done by `render_pdf.mjs` (Playwright/Chromium).

Usage:
    python scripts/docs/build_pdf_docs.py            # writes submission/pdf/*.pdf
    python scripts/docs/build_pdf_docs.py --html     # also keeps the intermediate HTML

Requires: pip install markdown pypdf ; node + playwright (npx playwright install chromium).
If node cannot find playwright from Python, render manually:
    NODE_PATH=<dir with playwright> node scripts/docs/render_pdf.mjs submission/pdf/_build/jobs.json
    python scripts/docs/build_pdf_docs.py --merge-only
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "submission" / "pdf"
BUILD = ROOT / "submission" / "pdf" / "_build"
REPO = "https://github.com/poggymacello/kendali"
VERSION = "1.2"
ISSUED = date(2026, 10, 20)

DOCS = [
    {
        "out": "Kendali_TechnicalDocumentation.pdf",
        "id": "KND-TD-001",
        "title": "Technical Documentation",
        "subtitle": "Architecture, core algorithms and security design of a policy-bounded AI treasury agent",
        "sources": ["docs/TECHNICAL_DOCUMENTATION.md"],
    },
    {
        "out": "Kendali_SecuritySelfAssessment.pdf",
        "id": "KND-SSA-001",
        "title": "Security Self-Assessment Report",
        "subtitle": "Permission tiers, threat model, controls, test evidence and known risks",
        "sources": ["docs/SECURITY_SELF_ASSESSMENT.md"],
    },
    {
        "out": "Kendali_ExecutionEvidence.pdf",
        "id": "KND-EE-001",
        "title": "Execution Evidence",
        "subtitle": "Public Sepolia transaction hashes and the reproducible 57-scenario evaluation",
        "sources": ["docs/EXECUTION_EVIDENCE.md", "reports/TESTNET_EVIDENCE.md", "reports/EVAL_REPORT.md"],
    },
]

HISTORY = [
    ("1.0", "10 Oct 2026", "Initial release with the submission package."),
    ("1.1", "19 Oct 2026", "Red-team round: 15 new probes, PO matching, tolerant extraction; suite 42 → 57 scenarios."),
    ("1.2", "20 Oct 2026", "Public Sepolia run (14/14 steps); execution evidence completed; PDF layout."),
]

CSS = r"""
@page { size: A4; margin: 22mm 18mm 20mm 18mm; }
:root { --ink:#1b2430; --muted:#5b6675; --accent:#0f5c4c; --accent2:#e3f0ec; --rule:#d6dbe1; --code:#f4f6f8; }
* { box-sizing: border-box; }
html { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: var(--ink); font-size: 10.2pt; line-height: 1.5; }
body { margin: 0; }
a { color: var(--accent); text-decoration: none; word-break: break-word; }
.cover { height: 297mm; padding: 28mm 22mm 20mm; display: flex; flex-direction: column; page-break-after: always;
         background: linear-gradient(160deg, #0f5c4c 0%, #12483f 55%, #0c2f2a 100%); color: #fff; }
.cover .brand { font-size: 11pt; letter-spacing: .18em; text-transform: uppercase; opacity: .85; }
.cover .event { margin-top: 4mm; font-size: 10pt; opacity: .8; }
.cover h1 { color: #fff; border: 0; font-size: 30pt; line-height: 1.15; margin: 42mm 0 6mm; font-weight: 700; }
.cover .sub { font-size: 13pt; max-width: 150mm; opacity: .92; }
.cover .tag { margin-top: 10mm; display: inline-block; padding: 2mm 4mm; border: 1px solid rgba(255,255,255,.5); border-radius: 2mm; font-size: 9pt; }
.cover .meta { margin-top: auto; display: grid; grid-template-columns: 40mm 1fr; row-gap: 2mm; font-size: 9.5pt; }
.cover .meta div:nth-child(odd) { opacity: .7; }
.cover .motto { margin-top: 10mm; font-size: 9.5pt; opacity: .75; font-style: italic; }
.control { page-break-after: always; }
h1, h2, h3, h4 { color: var(--accent); line-height: 1.25; page-break-after: avoid; }
h1.doc { font-size: 18pt; margin: 0 0 4mm; padding-bottom: 2mm; border-bottom: 2px solid var(--accent); }
h2 { font-size: 13.5pt; margin: 8mm 0 3mm; padding-bottom: 1.2mm; border-bottom: 1px solid var(--rule); }
h3 { font-size: 11.2pt; margin: 5mm 0 2mm; }
h4 { font-size: 10.4pt; margin: 4mm 0 1.5mm; }
.part { page-break-before: always; }
.part:first-of-type { page-break-before: auto; }
p { margin: 0 0 2.4mm; }
ul, ol { margin: 0 0 3mm 5mm; padding-left: 4mm; }
li { margin: .6mm 0; }
hr { border: 0; border-top: 1px solid var(--rule); margin: 5mm 0; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 8.8pt; page-break-inside: auto; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th { background: var(--accent); color: #fff; text-align: left; font-weight: 600; padding: 1.6mm 2mm; }
td { border-bottom: 1px solid var(--rule); padding: 1.4mm 2mm; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f8faf9; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.6pt; background: var(--code); padding: .2mm 1mm; border-radius: 1mm; word-break: break-all; }
pre { background: var(--code); border-left: 3px solid var(--accent); padding: 2.5mm 3mm; overflow: hidden; white-space: pre-wrap; word-break: break-all; font-size: 8.4pt; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { margin: 3mm 0; padding: 2mm 4mm; background: var(--accent2); border-left: 3px solid var(--accent); color: var(--ink); }
img { max-width: 100%; display: block; margin: 3mm auto; page-break-inside: avoid; }
.toc h2 { border: 0; }
.toc ol { list-style: none; margin: 0; padding: 0; }
.toc li { margin: 1.2mm 0; }
.toc li li { margin-left: 6mm; font-size: 9.4pt; }
.toc a { color: var(--ink); }
.small { font-size: 8.8pt; color: var(--muted); }
.kv { display: grid; grid-template-columns: 45mm 1fr; row-gap: 1.2mm; margin: 2mm 0 5mm; font-size: 9.4pt; }
.kv div:nth-child(odd) { color: var(--muted); }
"""


def rewrite_links(text: str, src: Path) -> str:
    """Relative repo links -> absolute GitHub links (a PDF has no repository next to it)."""
    def fix(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            return m.group(0)
        if label.startswith("!"):
            return m.group(0)
        rel = (src.parent / target.split("#")[0]).resolve()
        try:
            path = rel.relative_to(ROOT).as_posix()
        except ValueError:
            return m.group(0)
        kind = "tree" if rel.is_dir() else "blob"
        return f"[{label}]({REPO}/{kind}/main/{path})"
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", fix, text)


def embed_images(html_text: str, src: Path) -> str:
    def fix(m: re.Match) -> str:
        url = m.group(1)
        if re.match(r"^(https?:|data:|file:)", url):
            return m.group(0)
        p = (src.parent / url).resolve()
        return m.group(0).replace(url, p.as_uri())
    return re.sub(r'<img[^>]*src="([^"]+)"', fix, html_text)


def md_to_html(src: Path, part_idx: int) -> tuple[str, list[tuple[int, str, str]]]:
    text = src.read_text(encoding="utf-8")
    text = rewrite_links(text, src)
    lines = text.splitlines()
    doc_title = ""
    if lines and lines[0].startswith("# "):
        doc_title = lines[0][2:].strip()
        text = "\n".join(lines[1:])
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc", "attr_list"],
                           extension_configs={"toc": {"slugify": lambda v, s: f"p{part_idx}-" + re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")}})
    body = md.convert(text)
    body = embed_images(body, src)
    heads = []
    for tok in md.toc_tokens:
        heads.append((2, tok["name"], tok["id"]))
        for ch in tok.get("children", []):
            heads.append((3, ch["name"], ch["id"]))
    title_html = f'<h1 class="doc" id="part{part_idx}">{html.escape(doc_title)}</h1>' if doc_title else ""
    return f'<section class="part">{title_html}{body}</section>', [(1, doc_title, f"part{part_idx}")] + heads


def cover(d: dict) -> str:
    return f"""<style>@page {{ margin: 0; }}</style>
<div class="cover">
  <div class="brand">Kendali</div>
  <div class="event">2026 Shenzhen International FinTech Competition · International Track · Topic F — Agent Wallet</div>
  <h1>{html.escape(d['title'])}</h1>
  <div class="sub">{html.escape(d['subtitle'])}</div>
  <div><span class="tag">Public · Competition submission</span></div>
  <div class="meta">
    <div>Document ID</div><div>{d['id']}</div>
    <div>Version</div><div>{VERSION} · issued {ISSUED.strftime('%d %B %Y')}</div>
    <div>Team</div><div>Kendali · Institut Teknologi Bandung, Indonesia</div>
    <div>Authors</div><div>Poggy Macello Gultom (team lead) · Mohammad Ari Alexander Aziz</div>
    <div>Repository</div><div>{REPO}</div>
  </div>
  <div class="motto">The LLM proposes · the policy decides · the contract enforces</div>
</div>"""


def control_page(d: dict, toc: list[tuple[int, str, str]]) -> str:
    rows = "".join(f"<tr><td>{v}</td><td>{dt}</td><td>{html.escape(c)}</td></tr>" for v, dt, c in HISTORY)
    items, open_sub = [], False
    for lvl, name, anchor in toc:
        if not name:
            continue
        if lvl == 1:
            if open_sub:
                items.append("</ol></li>")
                open_sub = False
            items.append(f'<li><a href="#{anchor}"><b>{html.escape(name)}</b></a><ol>')
            open_sub = True
        elif lvl == 2:
            items.append(f'<li><a href="#{anchor}">{html.escape(name)}</a></li>')
    if open_sub:
        items.append("</ol></li>")
    toc_html = "".join(items)
    sources = ", ".join(f"<code>{s}</code>" for s in d["sources"])
    return f"""
<div class="control">
  <h1 class="doc">Document control</h1>
  <div class="kv">
    <div>Document</div><div>{html.escape(d['title'])} ({d['id']})</div>
    <div>Classification</div><div>Public — all companies, people, wallets and screening data are synthetic; tUSDC is a valueless test token</div>
    <div>Source of truth</div><div>{sources} in the repository (this PDF is generated from them)</div>
    <div>Reproduce</div><div><code>python eval/run_eval.py</code> · <code>pytest</code> · <code>forge test</code></div>
  </div>
  <table><thead><tr><th style="width:14mm">Version</th><th style="width:28mm">Date</th><th>Change</th></tr></thead><tbody>{rows}</tbody></table>
  <div class="toc"><h2>Contents</h2><ol>{toc_html}</ol></div>
</div>"""


def build_html(d: dict) -> tuple[str, str]:
    parts, toc = [], []
    for i, s in enumerate(d["sources"]):
        h, t = md_to_html(ROOT / s, i)
        parts.append(h)
        toc += t
    head = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Kendali — {html.escape(d['title'])}</title>
<style>{CSS}</style></head><body>"""
    return head + cover(d) + "</body></html>", head + control_page(d, toc) + "".join(parts) + "</body></html>"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--merge-only", action="store_true", help="skip HTML+render; merge PDFs already rendered from _build/jobs.json")
    ap.add_argument("--node-modules", default=None, help="folder containing playwright (default: resolve normally)")
    a = ap.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    manifest = BUILD / "jobs.json"
    if a.merge_only:
        jobs = json.loads(manifest.read_text(encoding="utf-8"))
        return merge(jobs, keep_html=a.html, manifest=manifest)
    jobs = []
    for d in DOCS:
        cover_html, body_html = build_html(d)
        stem = Path(d["out"]).stem
        cp, bp = BUILD / f"{stem}.cover.html", BUILD / f"{stem}.body.html"
        cp.write_text(cover_html, encoding="utf-8")
        bp.write_text(body_html, encoding="utf-8")
        jobs.append({"html": str(cp), "pdf": str(BUILD / f"{stem}.cover.pdf"), "plain": True})
        jobs.append({"html": str(bp), "pdf": str(BUILD / f"{stem}.body.pdf"),
                     "header": f"Kendali · {d['title']}", "footer": f"{d['id']} · v{VERSION} · Public"})
    manifest.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    env = None
    if a.node_modules:
        import os
        env = dict(os.environ, NODE_PATH=a.node_modules)
    r = subprocess.run(["node", str(Path(__file__).with_name("render_pdf.mjs")), str(manifest)], env=env)
    if r.returncode != 0:
        print("render failed; run: NODE_PATH=<dir with playwright> node scripts/docs/render_pdf.mjs "
              "submission/pdf/_build/jobs.json && python scripts/docs/build_pdf_docs.py --merge-only")
        return r.returncode
    return merge(jobs, keep_html=a.html, manifest=manifest)


def merge(jobs: list[dict], keep_html: bool, manifest: Path) -> int:
    from pypdf import PdfReader, PdfWriter
    for d in DOCS:
        stem = Path(d["out"]).stem
        w = PdfWriter()
        for part in ("cover", "body"):
            for pg in PdfReader(str(BUILD / f"{stem}.{part}.pdf")).pages:
                w.add_page(pg)
        w.add_metadata({"/Title": f"Kendali — {d['title']}", "/Author": "Team Kendali (ITB)",
                        "/Subject": f"{d['id']} v{VERSION}"})
        with open(OUT / d["out"], "wb") as fh:
            w.write(fh)
        print("merged", OUT / d["out"])
    for j in jobs:
        Path(j["pdf"]).unlink(missing_ok=True)
        if not keep_html:
            Path(j["html"]).unlink(missing_ok=True)
    if not keep_html:
        manifest.unlink(missing_ok=True)
        try:
            BUILD.rmdir()
        except OSError:
            pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
