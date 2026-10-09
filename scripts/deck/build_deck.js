// Build the Kendali final-presentation deck (≤10 minutes, 12 slides).
//   cd scripts/deck && npm install && NODE_PATH=./node_modules node build_deck.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL_THEME || "./apply_theme_local.js");

const ROOT = path.resolve(__dirname, "..", "..");
const IMG = (f) => path.join(ROOT, "docs", "img", f);
const OUT = path.join(ROOT, "submission", "Kendali_FinTechathon2026_Deck.pptx");
const TEAM = process.env.KENDALI_TEAM || "[TEAM NAME]";

const THEME = {
  name: "Kendali",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0F172A", lt1: "FFFFFF", dk2: "134E4A", lt2: "F1F5F9",
    accent1: "0F766E", accent2: "B45309", accent3: "B91C1C", accent4: "1D4ED8",
    accent5: "475569", accent6: "14B8A6", hlink: "0F766E", folHlink: "115E59",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.author = "Team Kendali";
pres.title = "Kendali — FinTechathon 2026";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "KD_TITLE",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 7.6, h: 1.4, fontSize: 60, bold: true, color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.55, w: 7.4, h: 1.6, fontSize: 22, color: "CBD5E1", valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "KD_CONTENT",
  background: { color: HEX.lt1 },
  margin: [0.4, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 1.3, fontSize: 34, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "Kendali · FinTechathon 2026 · Topic F", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: HEX.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5 },
});
pres.defineSlideMaster({
  title: "KD_CLOSING",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.0, w: 11.7, h: 1.2, fontSize: 48, bold: true, color: C.background1, margin: 0 }, text: "" } },
  ],
});

// ------------------------------------------------------------------ helpers
function card(slide, x, y, w, h, fill, name) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: "E2E8F0", width: 1 },
    shadow: { type: "outer", color: "94A3B8", opacity: 0.25, blur: 6, offset: 2, angle: 90 }, objectName: name,
  });
}
function badge(slide, x, y, d, color, label, size = 16) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color }, line: { color } });
  slide.addText(label, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: size, bold: true, color: "FFFFFF", margin: 0, isTextBox: true });
}
function text(slide, t, opts) {
  slide.addText(t, { margin: 0, isTextBox: true, valign: "top", ...opts });
}
function image(slide, file, x, y, w, h) {
  slide.addShape(pres.ShapeType.rect, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, fill: { color: "0F172A" }, line: { color: "CBD5E1", width: 1 } });
  slide.addImage({ path: IMG(file), x, y, w, h });
}

// ================================================================== 1 TITLE
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "KD_TITLE", sectionTitle: "Opening" });
text(s, "FINTECHATHON 2026  ·  INTERNATIONAL TRACK  ·  TOPIC F — AGENT WALLET", { x: 0.8, y: 1.2, w: 8.5, h: 0.4, fontSize: 13, bold: true, color: "5EEAD4", charSpacing: 1 });
s.addText("Kendali", { placeholder: "title" });
s.addText("An AI treasury agent that pays suppliers on-chain — and cannot be tricked into losing the money it controls.", { placeholder: "body" });
text(s, `Team ${TEAM}  ·  Institut Teknologi Bandung, Indonesia`, { x: 0.8, y: 6.35, w: 8, h: 0.4, fontSize: 15, color: "CBD5E1" });
const layers = [
  ["①  Understand", "LLM + deterministic NLU", HEX.accent4],
  ["②  Decide", "deterministic policy engine", HEX.accent2],
  ["③  Enforce", "KendaliVault smart contract", HEX.accent1],
];
layers.forEach(([h, sub, col], i) => {
  const y = 1.7 + i * 1.45;
  s.addShape(pres.ShapeType.roundRect, { x: 9.0, y, w: 3.6, h: 1.2, rectRadius: 0.14, fill: { color: col }, line: { color: col } });
  text(s, [{ text: h, options: { fontSize: 20, bold: true, color: "FFFFFF", breakLine: true } }, { text: sub, options: { fontSize: 13, color: "E2E8F0" } }],
    { x: 9.25, y: y + 0.2, w: 3.2, h: 0.85, valign: "middle" });
});
text(s, "the LLM proposes · the policy decides · the contract enforces", { x: 9.0, y: 6.0, w: 3.6, h: 0.5, fontSize: 12, italic: true, color: "94A3B8", align: "center" });
s.addNotes(
  "Good afternoon. We are team " + TEAM + " from Institut Teknologi Bandung, Indonesia. This is Kendali, which means 'control' in Indonesian. " +
  "Kendali is an AI agent that acts as the finance clerk of a small business. It reads invoices, pays suppliers on-chain and manages the treasury on its own. " +
  "And it is built so that it cannot be tricked into losing the money it controls. Our whole design fits in one sentence: the LLM proposes, the policy decides, the contract enforces."
);

// ================================================================== 2 PROBLEM
pres.addSection({ title: "Problem" });
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Problem" });
s.addText("Small exporters need an AI finance clerk — but a key makes it a target", { placeholder: "title" });
card(s, 0.6, 1.85, 5.6, 2.35, HEX.lt2, "persona");
text(s, "Meet Kopi Nusantara Roastery", { x: 0.9, y: 2.05, w: 5.0, h: 0.45, fontSize: 19, bold: true, color: HEX.dk1 });
text(s, "A Bandung coffee exporter with 9 staff and suppliers in Indonesia, Shenzhen and Singapore — and no finance team. One wrong payment wipes out a month of margin.",
  { x: 0.9, y: 2.6, w: 5.0, h: 1.5, fontSize: 15, color: "334155" });
text(s, "702,342", { x: 0.6, y: 4.45, w: 5.6, h: 1.0, fontSize: 60, bold: true, color: HEX.accent1 });
text(s, "scam reports to Indonesia's Anti-Scam Centre (OJK IASC), Nov 2024 – Sep 2026", { x: 0.6, y: 5.5, w: 5.4, h: 0.7, fontSize: 13, color: HEX.accent5 });
const threats = [
  ["1", HEX.accent3, "Documents that give orders", "Prompt injection: an invoice note tells the AI to ignore its rules and pay someone else."],
  ["2", HEX.accent2, "Invoices that change the wallet", "Business email compromise, look-alike addresses, fake vendors, duplicate “reminders”."],
  ["3", HEX.accent5, "Servers that get hacked", "If the agent's key is stolen, safety must not depend on the attacker behaving politely."],
];
threats.forEach(([n, col, h, d], i) => {
  const y = 1.85 + i * 1.65;
  card(s, 6.7, y, 6.0, 1.45, "FFFFFF", `threat${n}`);
  badge(s, 6.95, y + 0.42, 0.6, col, n, 18);
  text(s, h, { x: 7.8, y: y + 0.2, w: 4.7, h: 0.4, fontSize: 17, bold: true, color: HEX.dk1 });
  text(s, d, { x: 7.8, y: y + 0.62, w: 4.7, h: 0.75, fontSize: 14, color: "334155" });
});
s.addNotes(
  "Meet Kopi Nusantara Roastery, our persona: a coffee exporter in Bandung with nine staff and suppliers in three countries, and no finance team. " +
  "An AI agent that pays bills would save them hours every week. But an agent that holds a key becomes a target. " +
  "Fraud is everywhere: Indonesia's Anti-Scam Centre received over seven hundred thousand scam reports in under two years. " +
  "We see three ways to attack such an agent: documents that give it orders, invoices that quietly change the destination wallet, and servers that get hacked so the key itself is stolen. Kendali is designed against all three."
);

// ================================================================== 3 SOLUTION
pres.addSection({ title: "Solution" });
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Solution" });
s.addText("The LLM proposes, the policy decides, the contract enforces", { placeholder: "title" });
s.addImage({ path: IMG("architecture.png"), x: 1.28, y: 1.75, w: 10.78, h: 5.0 });
s.addNotes(
  "Here is the architecture. Layer one, Understand: an LLM — any OpenAI-compatible model, including DeepSeek or Qwen — together with a deterministic extractor turns invoices and chat into structured data from a closed set of intents. The model never sees a key and never chooses who gets paid. " +
  "Layer two, Decide: a deterministic policy engine binds every payee to its verified KYB wallet, screens addresses, detects fraud patterns, checks limits, liquidity and due dates, and simulates the exact transaction before signing. " +
  "Layer three, Enforce: our KendaliVault contract. Even if layers one and two are fully compromised, the agent's key can only pay allow-listed vendors within hard limits. The owner keeps a separate key for approvals, and every decision is hashed and anchored on-chain for audit."
);

// ================================================================== 4 CAPABILITIES
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Solution" });
s.addText("A real financial participant: what Kendali does on its own", { placeholder: "title" });
const caps = [
  ["Pays supplier invoices", "Reads text, PDF and JSON invoices in English and Bahasa Indonesia, verifies them and pays on-chain.", "T01 · T03 · T06 · T07"],
  ["Maker-checker", "Large, new or unusual payments become proposals; only the owner's key can approve them.", "T02 · T04 · T09"],
  ["Recurring obligations", "Rent, subscriptions and retainers are paid on their day — never twice in a period.", "T08 · T09 · T10"],
  ["Runs the treasury", "Keeps a runway for upcoming bills, parks idle cash in an ERC-4626 reserve, withdraws before paying.", "T11 · T12"],
  ["Talks like a colleague", "“Tolong bayar semua tagihan minggu ini” — chat in English or Indonesian, with reasons.", "T14 · T15 · T16 · T17"],
  ["Proves what it did", "Each decision is hashed before signing and anchored on-chain; one click verifies the trail.", "T18 · T19"],
];
caps.forEach(([h, d, ev], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.6 + col * 4.1, y = 1.85 + row * 2.55;
  card(s, x, y, 3.85, 2.3, "FFFFFF", `cap${i + 1}`);
  badge(s, x + 0.25, y + 0.25, 0.55, HEX.accent1, String(i + 1), 16);
  text(s, h, { x: x + 0.95, y: y + 0.3, w: 2.75, h: 0.5, fontSize: 17, bold: true, color: HEX.dk1, valign: "middle" });
  text(s, d, { x: x + 0.25, y: y + 0.95, w: 3.4, h: 0.95, fontSize: 14, color: "334155" });
  text(s, "eval: " + ev, { x: x + 0.25, y: y + 1.9, w: 3.4, h: 0.3, fontSize: 11, color: HEX.accent5, italic: true });
});
s.addNotes(
  "Kendali is not a chatbot — it is a financial participant that completes real tasks. It pays supplier invoices from text or PDF, in English or Indonesian. " +
  "Anything large, new or unusual becomes an on-chain proposal that only the owner can approve — classic maker-checker. It pays recurring obligations on their day and never twice. " +
  "It runs the treasury: keeps enough runway for upcoming bills and parks idle cash in an ERC-4626 reserve, withdrawing automatically before a payment. " +
  "The owner talks to it like a colleague, and every decision can be proven afterwards. Each card shows the evaluation scenarios that test it."
);

// ================================================================== 5 DEMO
pres.addSection({ title: "Demo" });
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Demo" });
s.addText("One instruction, thirteen invoices, zero losses", { placeholder: "title" });
image(s, "ui-assistant.png", 0.65, 1.95, 6.9, 4.31);
text(s, "“pay all invoices due this week”", { x: 7.95, y: 1.85, w: 4.8, h: 0.45, fontSize: 17, italic: true, color: HEX.dk1 });
const outcomes = [
  ["1", HEX.accent1, "paid automatically — all checks passed"],
  ["4", HEX.accent2, "sent to owner approval — large, new payee, anomaly, arithmetic"],
  ["1", HEX.accent5, "held — not due until 28 October"],
  ["7", HEX.accent3, "blocked — BEC, injection, duplicate, homoglyph, poisoning, unknown issuer, sanctions"],
];
outcomes.forEach(([n, col, label], i) => {
  const y = 2.45 + i * 0.98;
  text(s, n, { x: 7.95, y, w: 0.8, h: 0.85, fontSize: 44, bold: true, color: col, valign: "middle" });
  text(s, label, { x: 8.85, y: y + 0.08, w: 3.9, h: 0.75, fontSize: 14, color: "334155", valign: "middle" });
});
text(s, "Attacker wallets received 0 tUSDC · every block anchored on-chain", { x: 7.95, y: 6.4, w: 4.8, h: 0.45, fontSize: 13, bold: true, color: HEX.accent1 });
s.addNotes(
  "Here is the live console. The owner types one sentence: pay all invoices due this week. Thirteen invoices are waiting. " +
  "In a few seconds Kendali pays the one invoice that passes every check, sends four to the owner's approval queue — a large one, a new payee still in its cooling-off period, an amount anomaly and an invoice that does not add up — holds one that is not yet due, and blocks seven attacks. " +
  "The blocked ones include a business-email-compromise invoice with a changed wallet, a prompt injection hidden in the notes, a duplicate reminder, a homoglyph imitation of a real vendor, an address-poisoning decoy, an unknown issuer and a sanctioned counterparty. " +
  "Not a single token reached an attacker, and every blocked decision is anchored on-chain."
);

// ================================================================== 6 ATTACKS
pres.addSection({ title: "Security" });
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Security" });
s.addText("Every attack class we tested was stopped", { placeholder: "title" });
const head = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk1 } } });
const out = (t, col) => ({ text: t, options: { bold: true, color: col } });
const rows = [
  [head("Attack"), head("How Kendali detects it"), head("Outcome"), head("Test")],
  ["Business email compromise: new wallet + urgency", "Payee bound to the KYB wallet; pressure language flagged", out("BLOCK", HEX.accent3), "A01"],
  ["Prompt injection: English, Indonesian, zero-width split", "Deterministic scanner + LLM second opinion; documents are data", out("BLOCK", HEX.accent3), "A02 A14 A15"],
  ["Address poisoning (look-alike wallet)", "Prefix/suffix similarity to known vendor wallets", out("BLOCK", HEX.accent3), "A05"],
  ["Homoglyph vendor name", "Confusable characters folded and flagged", out("BLOCK", HEX.accent3), "A04"],
  ["Sanctioned counterparty (listed after onboarding)", "Screening of every address at payment time", out("BLOCK", HEX.accent3), "A07"],
  ["Duplicate “reminder” invoice", "Payment reference must be unique on-chain", out("BLOCK", HEX.accent3), "A03"],
  ["Inflated amount · bad arithmetic · above hard cap", "Vendor history, line-item maths, absolute cap", out("APPROVAL / BLOCK", HEX.accent2), "A08 A09 A23"],
  ["Chat: fake owner, raw address, raise limit, allowance", "Mandate checks run before — and override — the LLM", out("REFUSE", "7C3AED"), "A10–A13"],
  ["Stolen agent key: 6 on-chain attack variants", "KendaliVault rejects the transaction", out("REVERT", HEX.accent1), "A16–A21"],
  ["Tampering with the local audit log", "Hash chain + on-chain decision anchors", out("DETECTED", HEX.accent1), "A22"],
];
s.addTable(rows, {
  x: 0.6, y: 1.8, w: 12.1, colW: [4.2, 4.95, 1.75, 1.2], fontSize: 13, fontFace: "Calibri", color: "1E293B",
  border: { type: "solid", pt: 0.75, color: "E2E8F0" }, rowH: 0.44, valign: "middle", autoPage: false,
  fill: { color: "FFFFFF" },
});
s.addNotes(
  "We attacked our own agent systematically: twenty-three attack scenarios. Document-level attacks such as business email compromise, prompt injection in English and Indonesian — even split with invisible zero-width characters — address poisoning, homoglyph names, sanctioned vendors and duplicates are all blocked. " +
  "Suspicious but possibly legitimate cases, like an inflated amount, go to a human instead of being paid. " +
  "Chat attacks — pretending to be the owner, asking to pay a raw address, to raise a limit or to grant a token allowance — are refused by deterministic mandate checks that the LLM cannot override. " +
  "And with a stolen agent key, all six on-chain attack variants revert. Even tampering with our own audit log is detected."
);

// ================================================================== 7 TIERS
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Security" });
s.addText("Four permission tiers — the dangerous ones live on-chain", { placeholder: "title" });
const tiers = [
  ["T0", HEX.accent4, "Read-only", "Agent, anyone", "Balances, limits, payees, proposals, audit questions, simulations"],
  ["T1", HEX.accent1, "Autonomous within limits", "Agent key", "Pay allow-listed, cooled-off payees ≤ 1,000 each and ≤ 2,500 per day; treasury moves; pause"],
  ["T2", HEX.accent2, "Maker-checker", "Agent proposes · owner approves", "Payments up to 10,000, new payees, anything with a HIGH-risk finding"],
  ["T3", HEX.accent3, "Owner governance", "Owner key (multisig in production)", "Payees, limits (loosening waits 2 days), agent-key rotation, unpause"],
];
tiers.forEach(([t, col, name, who, what], i) => {
  const x = 0.6 + i * 3.08;
  card(s, x, 1.85, 2.85, 3.45, "FFFFFF", `tier${t}`);
  badge(s, x + 0.25, 2.05, 0.7, col, t, 16);
  text(s, name, { x: x + 0.25, y: 2.9, w: 2.4, h: 0.65, fontSize: 17, bold: true, color: HEX.dk1 });
  text(s, who, { x: x + 0.25, y: 3.55, w: 2.4, h: 0.5, fontSize: 13, italic: true, color: col });
  text(s, what, { x: x + 0.25, y: 4.05, w: 2.4, h: 1.2, fontSize: 13, color: "334155" });
});
card(s, 0.6, 5.6, 12.1, 1.15, HEX.lt2, "worstcase");
text(s, [
  { text: "Worst case with a stolen agent key:  ", options: { bold: true, color: HEX.accent3 } },
  { text: "pay only allow-listed vendors · at most 1,000 per payment · at most 2,500 per day · owner can pause or revoke the key instantly", options: { color: HEX.dk1 } },
], { x: 0.9, y: 5.75, w: 11.5, h: 0.85, fontSize: 16, valign: "middle" });
s.addNotes(
  "Permissions are tiered. Tier zero is read-only. Tier one is what the agent may do alone: pay allow-listed vendors that have passed a cooling-off period, at most one thousand per payment and two and a half thousand per day, plus treasury moves and the emergency pause. " +
  "Tier two is maker-checker: the agent proposes, the owner approves. Tier three is governance and belongs only to the owner, and loosening a limit is time-locked for two days. " +
  "The key point: tiers one to three are enforced by the smart contract, not by the prompt. So the worst case with a stolen agent key is small and bounded — and the owner can pause or revoke the key at once."
);

// ================================================================== 8 VAULT
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Security" });
s.addText("KendaliVault: guardrails the AI cannot argue with", { placeholder: "title" });
image(s, "ui-redteam.jpg", 0.65, 1.95, 6.7, 4.19);
text(s, "Live red-team with a stolen agent key: every call rejected by the contract", { x: 0.6, y: 6.25, w: 6.8, h: 0.4, fontSize: 12, italic: true, color: HEX.accent5 });
text(s, [
  { text: "Allow-list with a cooling-off period for new payees", options: { bullet: true, breakLine: true } },
  { text: "1,000 per payment and 2,500 per day for the agent alone", options: { bullet: true, breakLine: true } },
  { text: "Proposals up to 10,000; only the owner approves", options: { bullet: true, breakLine: true } },
  { text: "Loosening limits waits 2 days; tightening is instant", options: { bullet: true, breakLine: true } },
  { text: "Circuit breaker: agent can pause, only the owner resumes", options: { bullet: true, breakLine: true } },
  { text: "Every action carries the hash of its decision", options: { bullet: true } },
], { x: 7.75, y: 1.9, w: 5.0, h: 3.0, fontSize: 15, color: HEX.dk1, paraSpaceAfter: 6 });
card(s, 7.75, 5.05, 4.95, 1.6, HEX.lt2, "invariants");
text(s, [
  { text: "Proven by stateful fuzzing (8,192 random calls per run)", options: { bold: true, color: HEX.accent1, breakLine: true } },
  { text: "attacker never paid · daily outflow ≤ limit · governance unchanged · custody conserved", options: { color: "334155" } },
], { x: 7.95, y: 5.2, w: 4.6, h: 1.3, fontSize: 13 });
s.addNotes(
  "This is the contract layer, KendaliVault. On the left you see our live red-team button: we sign attacks with the agent's own key — pay the attacker, pay above the limit, add a payee, raise limits, approve our own proposal, unpause — and the contract rejects every one, with a precise custom error. " +
  "The rules are simple: an allow-list with cooling-off, solo limits per payment and per day, owner approval above that, a two-day timelock on loosening, and a circuit breaker. " +
  "We did not just unit-test this. Stateful fuzzing throws thousands of random call sequences at the vault, and four invariants always hold: the attacker is never paid, daily outflow never exceeds the limit, governance never changes and custody is conserved."
);

// ================================================================== 9 EVALUATION
pres.addSection({ title: "Evidence" });
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Evidence" });
s.addText("Measured, not claimed: 42 of 42 scenarios pass", { placeholder: "title" });
const stats = [
  ["100%", "task completion", "19 of 19 legitimate tasks done end-to-end", HEX.accent1],
  ["100%", "attack prevention", "23 of 23 attacks stopped or safely routed", HEX.accent3],
  ["0", "tUSDC to attackers", "in every scenario, including a stolen key", HEX.dk1],
];
stats.forEach(([big, label, sub, col], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.85, 3.85, 2.0, "FFFFFF", `stat${i}`);
  text(s, big, { x: x + 0.3, y: 1.95, w: 3.3, h: 0.95, fontSize: 52, bold: true, color: col });
  text(s, label, { x: x + 0.3, y: 2.88, w: 3.3, h: 0.35, fontSize: 16, bold: true, color: HEX.dk1 });
  text(s, sub, { x: x + 0.3, y: 3.23, w: 3.3, h: 0.5, fontSize: 13, color: HEX.accent5 });
});
s.addChart(pres.ChartType.bar, [{ name: "passing", labels: ["Smart-contract tests", "Python tests", "Evaluation scenarios"], values: [18, 55, 42] }], {
  x: 0.6, y: 4.1, w: 6.6, h: 2.7, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: "1E293B", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt",
  showTitle: true, title: "Tests passing (all suites 100% green)", titleFontSize: 13, titleColor: "1E293B", titleFontFace: "+mn-lt",
  catAxisLabelColor: "334155", catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true,
  valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
});
card(s, 7.6, 4.1, 5.1, 2.7, HEX.lt2, "repro");
text(s, [
  { text: "Reproducible by the judges", options: { bold: true, color: HEX.dk1, fontSize: 16, breakLine: true } },
  { text: "python eval/run_eval.py   ·   pytest   ·   forge test", options: { fontFace: "Courier New", fontSize: 12, color: HEX.accent1, breakLine: true } },
  { text: "Each scenario runs on a fresh EVM snapshot: 91 real transactions in 23 seconds, no API key needed. Public-testnet hashes in reports/TESTNET_EVIDENCE.md.", options: { fontSize: 13, color: "334155" } },
], { x: 7.85, y: 4.3, w: 4.6, h: 2.35, paraSpaceAfter: 8 });
s.addNotes(
  "Everything we just claimed is measured. Our evaluation harness runs forty-two scenarios — nineteen legitimate tasks and twenty-three attacks — each on a fresh blockchain snapshot. All forty-two pass: one hundred percent task completion, one hundred percent attack prevention, and zero tokens to any attacker wallet. " +
  "Underneath that sit eighteen smart-contract tests including fuzzing and invariants, and fifty-five Python tests, including the LLM path and an end-to-end on-chain run. " +
  "Judges can reproduce everything with three commands and no API key, and our public-testnet run provides real transaction hashes, including a reverted stolen-key transaction."
);

// ================================================================== 10 COMPLIANCE
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Evidence" });
s.addText("Bank-grade controls, verifiable on-chain", { placeholder: "title" });
const ctrl = [
  [head("Control objective"), head("Kendali implementation")],
  ["Four-eyes / maker-checker", "propose() by agent · approveProposal() by owner only"],
  ["Segregation of duties", "separate agent, owner and deployer keys"],
  ["Beneficiary verification (anti-BEC)", "payee bound to KYB record; changed details → block + call-back"],
  ["New-beneficiary cooling-off", "payeeCooldown enforced on-chain"],
  ["Sanctions / AML screening", "every address screened at payment time"],
  ["Limits and change management", "per-payment, daily and hard caps; time-locked loosening"],
  ["Kill switch", "pause by agent or owner; only the owner resumes"],
  ["Explainability and record keeping", "reason codes + EN/ID explanation, hashed and anchored"],
];
s.addTable(ctrl, {
  x: 0.6, y: 1.8, w: 7.3, colW: [2.9, 4.4], fontSize: 13, fontFace: "Calibri", color: "1E293B",
  border: { type: "solid", pt: 0.75, color: "E2E8F0" }, rowH: 0.52, valign: "middle", autoPage: false, fill: { color: "FFFFFF" },
});
const flow = [
  ["Decision record", "findings · action · amount · explanation", HEX.accent4],
  ["keccak256 → decisionHash", "computed before anything is signed", HEX.accent2],
  ["Carried inside the transaction", "AutoPaid · ProposalCreated · DecisionCommitted", HEX.accent1],
  ["verify()", "recompute every hash, check the chain", HEX.dk1],
];
flow.forEach(([h, d, col], i) => {
  const y = 1.85 + i * 1.22;
  s.addShape(pres.ShapeType.roundRect, { x: 8.4, y, w: 4.3, h: 0.95, rectRadius: 0.1, fill: { color: col }, line: { color: col } });
  text(s, [{ text: h, options: { bold: true, fontSize: 15, color: "FFFFFF", breakLine: true } }, { text: d, options: { fontSize: 12, color: "E2E8F0" } }],
    { x: 8.6, y: y + 0.1, w: 3.9, h: 0.78, valign: "middle" });
  if (i < 3) s.addShape(pres.ShapeType.downArrow, { x: 10.4, y: y + 0.97, w: 0.3, h: 0.23, fill: { color: "94A3B8" }, line: { color: "94A3B8" } });
});
s.addNotes(
  "For a bank, controls matter as much as features. Kendali implements the controls a treasury department would expect: four-eyes approval, segregation of duties, beneficiary verification against business email compromise, cooling-off for new beneficiaries, sanctions screening, limits with time-locked changes, and a kill switch. " +
  "On the right is what makes the AI auditable: every decision record is hashed before signing, the hash travels inside the transaction, and anyone can later recompute it and check it against the chain. That turns the AI's reasoning into verifiable evidence."
);

// ================================================================== 11 CRITERIA
s = pres.addSlide({ masterName: "KD_CONTENT", sectionTitle: "Evidence" });
s.addText("Mapped to the judging criteria", { placeholder: "title" });
const crit = [
  ["Task completion · 40%", HEX.accent1, [
    "19/19 legitimate tasks completed end-to-end with real transactions",
    "Invoices in EN/ID, text and PDF; maker-checker; recurring; treasury; chat",
    "Public-testnet execution log with transaction hashes",
  ]],
  ["Security & compliance · 30%", HEX.accent3, [
    "Three independent layers; four permission tiers enforced on-chain",
    "23/23 attacks stopped, including a stolen agent key",
    "Fuzz-proven invariants; honest risk register in the self-assessment",
  ]],
  ["Innovation & interaction · 30%", HEX.accent4, [
    "Decision hashes anchored on-chain: verifiable AI",
    "Bilingual chat for Indonesian SMEs; one-click red-team and audit",
    "Works with any OpenAI-compatible model, including DeepSeek and Qwen",
  ]],
];
crit.forEach(([h, col, items], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.85, 3.85, 3.65, "FFFFFF", `crit${i}`);
  s.addShape(pres.ShapeType.roundRect, { x: x + 0.25, y: 2.05, w: 3.35, h: 0.6, rectRadius: 0.08, fill: { color: col }, line: { color: col } });
  text(s, h, { x: x + 0.25, y: 2.05, w: 3.35, h: 0.6, fontSize: 15, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
  text(s, items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
    { x: x + 0.3, y: 2.85, w: 3.3, h: 2.55, fontSize: 14, color: "334155", paraSpaceAfter: 8 });
});
card(s, 0.6, 5.75, 12.1, 1.0, HEX.lt2, "bonus");
text(s, [
  { text: "On-chain challenge bonus:  ", options: { bold: true, color: HEX.accent1 } },
  { text: "custom policy vault + ERC-4626 treasury + on-chain decision anchoring + a stolen-key transaction reverted on a public testnet", options: { color: HEX.dk1 } },
], { x: 0.9, y: 5.85, w: 11.5, h: 0.8, fontSize: 15, valign: "middle" });
s.addNotes(
  "To make your evaluation easy, here is how Kendali maps to the three criteria. Task completion: nineteen real tasks done end-to-end with on-chain transactions. Security and compliance: three independent layers, four permission tiers enforced on-chain, twenty-three attacks stopped and invariants proven by fuzzing — plus an honest list of residual risks. " +
  "Innovation and interaction: on-chain decision anchoring makes the AI verifiable, the bilingual chat fits Indonesian small businesses, and it runs on any OpenAI-compatible model. For the on-chain challenge we built a custom policy vault and a reserve, not just a wallet call."
);

// ================================================================== 12 CLOSING
pres.addSection({ title: "Closing" });
s = pres.addSlide({ masterName: "KD_CLOSING", sectionTitle: "Closing" });
s.addText("Autonomy you can verify", { placeholder: "title" });
const next = [
  ["Production path", "multisig owner + session keys · live sanctions feeds · OCR and e-invoices"],
  ["Settlement", "tokenized deposits or licensed stablecoins on permissioned EVM chains (e.g. FISCO BCOS)"],
  ["Pilot", "cross-border SMEs in Indonesia, Singapore and Shenzhen"],
];
next.forEach(([h, d], i) => {
  const y = 2.6 + i * 1.05;
  badge(s, 0.8, y + 0.08, 0.55, HEX.accent6, String(i + 1), 15);
  text(s, [{ text: h + "   ", options: { bold: true, color: "FFFFFF" } }, { text: d, options: { color: "CBD5E1" } }],
    { x: 1.6, y, w: 10.8, h: 0.75, fontSize: 18, valign: "middle" });
});
text(s, `Thank you — Team ${TEAM} · Institut Teknologi Bandung`, { x: 0.8, y: 6.05, w: 8, h: 0.45, fontSize: 17, bold: true, color: "5EEAD4" });
text(s, "Code, evaluation and evidence: github.com/[team]/kendali", { x: 0.8, y: 6.5, w: 8, h: 0.4, fontSize: 14, color: "94A3B8" });
s.addNotes(
  "To close: Kendali shows that an AI agent can be a real financial participant — paying, approving, saving — while every dangerous power stays behind rules it cannot argue with, and every decision stays verifiable. " +
  "Our path to production is a multisig owner with session keys, live sanctions feeds and settlement in regulated instruments such as tokenized deposits on permissioned EVM chains like FISCO BCOS, piloting with cross-border small businesses between Indonesia, Singapore and Shenzhen. " +
  "Autonomy you can verify. Thank you — we are happy to take your questions."
);

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
