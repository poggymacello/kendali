# Email drafts for the organisers (FinTechathon 2026, International Track)

Official mailbox: **fintechathon@ican-x.com** (general contact: info@ican-x.com).
The registration form says: subject **"International Track Registration – Team Name – Team Leader Name"**, reply within 48 hours.
Deadline for registration **and** submission: **20 Oct 2026, 23:59 Beijing time = 22:59 WIB**.

Fill everything in `[brackets]` yourself. Do not send anything you have not checked.

---

## Email 1: registration ✅ sent 19 Oct 2026

Kept below for reference only.

<details><summary>Email 1 text</summary>



**To:** fintechathon@ican-x.com
**Subject:** International Track Registration – Kendali – [Team Leader Full Name]

**Attachments:**
1. `registration-form-TOFILL.xlsx`, filled in and renamed, e.g. `Kendali_International_Registration_Form.xlsx` (Attachment 3, all members, leader signature + date)
2. Passport bio-page image for each member, e.g. `Kendali_[Name]_Passport.jpg` (the form asks for it in column L)
3. Proof of enrolment for each member (student card / KTM, or a letter of active enrolment), e.g. `Kendali_[Name]_Enrollment.pdf`
4. *(optional)* `team-information-form-TOFILL.xlsx`, filled in, because the website's process page links this second form as well

**Body:**

> Dear Organising Committee,
>
> Please find attached the International Track registration for team Kendali from Institut Teknologi Bandung, Indonesia. We have chosen Topic F (Agent Wallet). Our entry title is "Kendali: A Policy-Bounded AI Treasury Agent for Small Businesses".
>
> Attached are the completed registration form, a passport bio-page image and proof of enrolment for every team member.
>
> We would also be grateful if you could confirm three points:
> 1. Should the full submission (GitHub link, technical document, deck, demo video, security self-assessment and execution evidence) be sent by email to this address before 20 October, 23:59 Beijing time? If the video is large, is a download link acceptable?
> 2. For Topic F, are transaction hashes on a public Ethereum testnet (Sepolia) accepted as on-chain execution evidence?
> 3. If our team is selected as a finalist, can the committee provide an invitation letter for visa purposes?
>
> Thank you for organising the competition.
>
> Best regards,
> [Team Leader Full Name]
> Team Leader, Kendali
> Institut Teknologi Bandung, Indonesia
> [Phone / WhatsApp]

</details>

---

## Email 2: full submission (send Tue 20 Oct, by 18:00 WIB; hard deadline 22:59 WIB = 23:59 Beijing)

**How to send:** open the thread of Email 1 in Gmail → **Reply** (keeps the same subject thread so they can match the team) → change the subject to the one below. The rules say the latest version received before the deadline counts, so sending early is safe.

**To:** fintechathon@ican-x.com
**Subject:** `International Track Submission – Kendali – Topic F – Poggy Macello Gultom`

**Attach these 4 PDFs** (all in `submission/pdf/`, ≈2 MB in total, well under Gmail's 25 MB):
| # | File | Rule item it answers |
|---|---|---|
| 1 | `Kendali_TechnicalDocumentation.pdf` (KND-TD-001) | (1) technical documentation: architecture, core algorithms, security design |
| 2 | `Kendali_FinTechathon2026_Deck.pdf` (13 slides, ≈9.5 min) | (2) presentation deck ≤10 min |
| 3 | `Kendali_SecuritySelfAssessment.pdf` (KND-SSA-001) | (5) security self-assessment: permission tiers + known risks |
| 4 | `Kendali_ExecutionEvidence.pdf` (KND-EE-001) | (6) execution evidence: real Sepolia transaction hashes + 57-scenario evaluation |

Optional 5th attachment: `Kendali_FinTechathon2026_Deck.pptx` (editable original). **Links in the body:** (3) demo video, (4) source code.

**Body (fill the two `[ ]` items, nothing else):**

> Dear Organising Committee,
>
> Team Kendali (Institut Teknologi Bandung, Indonesia) submits its entry for the International Track, Topic F: Agent Wallet. Team: Poggy Macello Gultom (team leader) and Mohammad Ari Alexander Aziz.
>
> **Entry:** Kendali: A Policy-Bounded AI Treasury Agent for Small Businesses. The LLM proposes, a deterministic policy engine decides, and a smart-contract vault enforces the limits, so even a stolen agent key cannot move funds to an attacker.
>
> **Required materials:**
> 1. Technical documentation: attached (Kendali_TechnicalDocumentation.pdf)
> 2. Presentation deck (under 10 minutes): attached (Kendali_FinTechathon2026_Deck.pdf)
> 3. Demo video (under 5 minutes): [video link, set to "anyone with the link can view"]
> 4. Source code with README, deployment guide and test cases: https://github.com/poggymacello/kendali
> 5. Security self-assessment: attached (Kendali_SecuritySelfAssessment.pdf)
> 6. Execution evidence: attached (Kendali_ExecutionEvidence.pdf)
>
> **On-chain execution evidence (Ethereum Sepolia, public testnet, 20 October 2026):**
> - Vault contract: https://sepolia.etherscan.io/address/0x7240Dd6E8C95BcE6A1CE53BCD44781585bC067D7
> - Autonomous agent payment of a verified invoice: https://sepolia.etherscan.io/tx/0x3f1fd6babd6a62ec556099683e3675d8517137d088637ca87e90982f675e4a4a
> - Owner approval of a large payment (maker-checker): https://sepolia.etherscan.io/tx/0xb4f7e6391fe91fdfab9049088d8275901837698c36449528354daed07968e66c
> - Payment attempted with a stolen agent key, reverted by the contract: https://sepolia.etherscan.io/tx/0x433d65fd8eaa577b8af68b094801f4866ccc1b88ca87b67ea258c04b3c3eb3dd
> - All 14 steps with every transaction hash: https://github.com/poggymacello/kendali/blob/main/reports/TESTNET_EVIDENCE.md
>
> **Results, reproducible from a clean clone:** 57 of 57 evaluation scenarios pass (22 tasks, 35 attacks), task completion 100%, attack prevention 100%, attacker wallets never funded; 84 Python tests and 18 smart-contract tests pass. Three commands reproduce everything: `python eval/run_eval.py`, `pytest`, `forge test`. No API key or real funds are needed.
>
> All companies, people and wallets in the demo are synthetic, and tUSDC is a valueless test token.
>
> Could you please confirm that you have received our submission?
>
> Best regards,
> Poggy Macello Gultom
> Team Leader, Kendali
> Institut Teknologi Bandung, Indonesia
> +62 853-6104-8752

**Before you press Send:**
- [ ] Video link opens in an incognito window (no login needed) and is under 5:00.
- [ ] https://github.com/poggymacello/kendali opens in an incognito window (public).
- [ ] The 4 PDFs are attached and open.
- [ ] Sent from gultompoggy@gmail.com, as a reply in the Email 1 thread.
- [ ] After sending: if there's no confirmation within 24 h, reply once asking them to confirm receipt.

---

## Optional: proposal summary for the form (field I.6, 100–200 words)

The field is optional. The draft below describes what the code actually does. Edit it into your own words before you paste it. Word count: about 150.

> Kendali is an AI agent that runs the payables and treasury of a small cross-border business. It reads supplier invoices (text, PDF or JSON) and owner instructions in English or Bahasa Indonesia, pays suppliers on-chain, handles recurring bills and parks idle cash in an ERC-4626 reserve. The language model only proposes. A deterministic policy engine decides, checking each payment against the verified vendor wallet, open purchase orders, a screening list, fraud detectors (business email compromise, prompt injection, look-alike addresses, duplicates) and spending limits, and it simulates the transaction before signing. A smart-contract vault enforces the hard limits, so even a stolen agent key can only pay allow-listed vendors within small caps. Larger payments need the owner's approval. Every decision is hashed and anchored on-chain for audit. We test it with 57 automated scenarios (22 tasks, 35 attacks), 84 Python tests and 18 contract tests, and we publish real Sepolia transaction hashes.
