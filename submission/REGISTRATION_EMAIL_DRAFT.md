# Email drafts for the organisers (FinTechathon 2026, International Track)

Official mailbox: **fintechathon@ican-x.com** (general contact: info@ican-x.com).
The registration form says: subject **"International Track Registration – Team Name – Team Leader Name"**, reply within 48 hours.
Deadline for registration **and** submission: **20 Oct 2026, 23:59 Beijing time = 22:59 WIB**.

Fill everything in `[brackets]` yourself. Do not send anything you have not checked.

---

## Email 1: registration (send today, 19 Oct)

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

---

## Email 2: full submission (send on 20 Oct, aim for 18:00 WIB at the latest)

The rules say the latest version received before the deadline counts, so it is safe to send early and update later. Reply in the **same thread** as Email 1 so they can match the team.

**To:** fintechathon@ican-x.com
**Subject:** International Track Submission – Kendali – Topic F – [Team Leader Full Name]

**Attachments** (keep the email under ~20 MB; share bigger files as links):
1. `Kendali_TechnicalDocumentation.pdf` (export of `docs/TECHNICAL_DOCUMENTATION.md`)
2. `Kendali_FinTechathon2026_Deck.pptx` (+ a PDF export of it)
3. `Kendali_SecuritySelfAssessment.pdf` (export of `docs/SECURITY_SELF_ASSESSMENT.md`)
4. `Kendali_ExecutionEvidence.pdf` (export of `docs/EXECUTION_EVIDENCE.md` + `reports/TESTNET_EVIDENCE.md`)
5. Demo video as a link (file name `InternationalAI-Kendali-DemoVideo.mp4`, the format the official video guide suggests)

**Body:**

> Dear Organising Committee,
>
> Team Kendali (Institut Teknologi Bandung, Indonesia, Topic F: Agent Wallet) submits its entry for the International Track.
>
> - Source code (README, deployment instructions, test cases): [https://github.com/poggymacello/kendali]
> - Demo video (under 5 minutes): [video link]
> - Attached: technical documentation, presentation deck, security self-assessment, execution evidence
> - On-chain evidence: our agent's transactions on the Sepolia testnet, with explorer links, are listed in reports/TESTNET_EVIDENCE.md in the repository. Vault contract: [0x... vault address from the report]
>
> Everything can be reproduced from a clean machine with three commands (python eval/run_eval.py, pytest, forge test). No API key or real funds are needed.
>
> Please let us know if you need anything else.
>
> Best regards,
> [Team Leader Full Name]
> Team Leader, Kendali

---

## Optional: proposal summary for the form (field I.6, 100–200 words)

The field is optional. The draft below describes what the code actually does. Edit it into your own words before you paste it. Word count: about 150.

> Kendali is an AI agent that runs the payables and treasury of a small cross-border business. It reads supplier invoices (text, PDF or JSON) and owner instructions in English or Bahasa Indonesia, pays suppliers on-chain, handles recurring bills and parks idle cash in an ERC-4626 reserve. The language model only proposes. A deterministic policy engine decides, checking each payment against the verified vendor wallet, open purchase orders, a screening list, fraud detectors (business email compromise, prompt injection, look-alike addresses, duplicates) and spending limits, and it simulates the transaction before signing. A smart-contract vault enforces the hard limits, so even a stolen agent key can only pay allow-listed vendors within small caps. Larger payments need the owner's approval. Every decision is hashed and anchored on-chain for audit. We test it with 57 automated scenarios (22 tasks, 35 attacks), 84 Python tests and 18 contract tests, and we publish real Sepolia transaction hashes.
