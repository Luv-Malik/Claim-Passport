<div align="center">

<img src="docs/assets/banner.svg" alt="Claim Passport" width="100%">

<br>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#-quick-start)
[![Flask](https://img.shields.io/badge/Backend-Flask-000000?logo=flask&logoColor=white)](#-architecture)
[![Frontend](https://img.shields.io/badge/Frontend-plain%20JS%2C%20no%20build-F7DF1E?logo=javascript&logoColor=black)](#-architecture)
[![Tests](https://img.shields.io/badge/tests-88%20passing-1fa463)](#-by-the-numbers)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-working%20prototype-C75B0B)](#-honest-limits)

**[🚀 Quick start](#-quick-start)** ·
**[📸 Screenshots](#-see-it-in-action)** ·
**[✨ Features](#-features)** ·
**[🔄 How it works](#-how-it-works)** ·
**[👥 Roles](#-who-can-do-what)** ·
**[🏗 Architecture](#-architecture)** ·
**[🔌 API](#-api-in-30-seconds)** ·
**[⚠️ Limits](#-honest-limits)** ·
**[🧠 Round 3](#-whats-new-in-round-3)** ·
**[☁️ Deploy](#-deploy)** ·
**[🗺 Roadmap](#-roadmap)**

</div>

---

## 💡 The idea in one minute

Companies publish content through many writers, agencies and AI tools. Wrong facts, old prices and claims nobody can prove slip through, and **a claim that was true on publishing day can become false later** ("Plans start at Rs. 499", "10,000+ customers", "ISO certified").

**Claim Passport** checks content *before* it goes live, explains every problem with its source, and suggests fixes that keep the writer's meaning. After publishing, every verified claim carries a **passport** (source, owner, expiry, live status). When a source changes, the platform finds every page that is now wrong and prepares a fix. **A person always decides.**

| | 😬 Without it | ✅ With Claim Passport |
|---|---|---|
| **Before publishing** | Manual review, inconsistent feedback | Instant checks with a reason, a source and a fix for every issue |
| **Wrong numbers** | Found by customers | Compared with the approved fact, fixed in one click |
| **After publishing** | Nobody re-checks old pages | Source change → affected pages flagged → fix ready |
| **AI use** | Hidden | Every AI or outside service call is logged and disclosed |
| **Accountability** | "Who approved this?" | Full audit trail and a Proof Time Machine |

<div align="center">
<img src="docs/screenshots/02-dashboard.png" alt="Dashboard" width="92%">
<br><sub>The dashboard: Truth Debt gauge, claim health, content pipeline, and what will go stale next.</sub>
</div>

---

## 📸 See it in action

<table>
<tr>
<td width="50%"><img src="docs/screenshots/03-review-workspace.png" alt="Review workspace"><br><b>🧑‍💻 Review workspace</b><br><sub>Brand score, quality radar, progress, step tracker and highlighted text.</sub></td>
<td width="50%"><img src="docs/screenshots/04-findings.png" alt="Findings with fixes"><br><b>🔎 Explained findings</b><br><sub>Each issue shows its rule or fact, a confidence level and a before/after preview.</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/05-claim-passports.png" alt="Claim passports"><br><b>🛂 Claim Passports</b><br><sub>Every published claim linked to its source, with an expiry bar.</sub></td>
<td><img src="docs/screenshots/06-insights.png" alt="Insights"><br><b>📊 Insights</b><br><sub>Repeated mistakes, team patterns and guidelines that may be unclear.</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/07-proof-time-machine.png" alt="Proof Time Machine"><br><b>⏳ Proof Time Machine</b><br><sub>Pick a page and a date: what was live, which source backed it, who approved it.</sub></td>
<td><img src="docs/screenshots/08-truth-feed.png" alt="Truth Feed"><br><b>🌐 Truth Feed</b><br><sub>Verified facts that AI assistants can read, so they quote current information.</sub></td>
</tr>
</table>

<details>
<summary><b>🎨 More screens: new review, Brand Vault, login, dark mode, mobile</b></summary>
<br>
<table>
<tr>
<td width="50%"><img src="docs/screenshots/09-new-review.png" alt="New review"><br><sub><b>New review</b>: paste or drag and drop a file, or try a sample.</sub></td>
<td width="50%"><img src="docs/screenshots/10-brand-vault.png" alt="Brand Vault"><br><sub><b>Brand Vault</b>: searchable fact cards with expiry bars.</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/11-dark-mode.png" alt="Dark mode"><br><sub><b>Dark mode</b> (one click in the top bar).</sub></td>
<td><img src="docs/screenshots/01-login.png" alt="Login"><br><sub><b>Login</b> with one-tap demo accounts.</sub></td>
</tr>
</table>
<p align="center"><img src="docs/screenshots/12-mobile.png" alt="Mobile" width="260"><br><sub>Works on a phone too.</sub></p>
</details>

---

## ✨ Features

| | Feature | What it does |
|---|---|---|
| 📚 | **Brand Vault** | Approved facts (source, owner, expiry, version history), rules imported from a markdown guideline file, glossary, brand assets |
| 📄 | **Many file types** | Text, Markdown, HTML, PDF, Word, PowerPoint, PNG/JPG/WebP (OCR reads text inside images) |
| 🔎 | **Claim finder** | Spots numbers, prices, superlatives ("best"), absolutes ("100%", "24x7"), certificates and comparisons |
| ✅ | **Fact checker** | Matches each claim to an approved fact, compares numbers by value and kind, understands "over 5,000" vs "10,000+" |
| 🧪 | **19 built-in checks** | Tone, terminology, messaging, accessibility (WCAG contrast, alt text, links, reading ease), visual (colours, fonts, image size/shape) |
| 💬 | **Explain + suggest** | Plain reason, exact guideline or fact (with page), confidence, and a fix that changes only the problem phrase |
| 👤 | **Human control** | Nothing applies until a person accepts. Locked claims (price, legal, certificates, comparisons) need a reviewer |
| 🔁 | **Review workflow** | Draft → In review → Approved → Published, with versions, word-level diff, comments, approvals, audit trail |
| 🛂 | **Claim Passports** | Live status per claim: 🟢 valid · 🟡 expiring · 🔴 source changed · 🔴 expired · 🟣 no source |
| 🐕 | **Source-change watcher** | "Dependabot for claims": change a fact and every affected page is flagged with a ready fix |
| 📉 | **Truth Debt + half-life** | One score for how much live content is out of date, and a forecast of what goes stale next |
| 🌐 | **Truth Feed** | Public `/.well-known/claims.json` of verified, non-confidential, non-expired facts for AI tools |
| ⏳ | **Proof Time Machine** | See what was live on any date, which sources backed it, and who approved it |
| 📊 | **Insights** | Repeated mistakes by rule and team, and an "unclear guideline" detector with evidence |
| 🔒 | **Privacy** | Roles, confidential facts, personal-data masking, and an AI Transparency log |
| 🎯 | **Hybrid checking + Accuracy Lab** | Meaning-aware matching, implied claims, optional cited AI judge, and a measured benchmark page |
| 🔔 | **Alerts + scheduler** | Email, Slack, signed webhook, weekly digest, background scan, retries |
| 📑 | **PDF page view, OCR, corrected export** | Outlined problems on the real PDF page, scanned-PDF OCR, corrected .docx/.pptx download |
| ⌨️ | **Friendly UI** | `Ctrl+K` command palette, `j` `k` `a` `r` shortcuts, "Fix easy ones" in one click, light/dark, mobile |

<details>
<summary><b>📋 Coverage of the Inkloom AI problem statement</b></summary>

| Requirement | Status | Where |
|---|:---:|---|
| Import or define guidelines, approved facts, terminology, assets | ✅ | `vault.py` |
| Review text, images, documents | ✅ | `ingest.py` |
| Detect tone, language, facts, claims, visuals, accessibility | ✅ | `engine/` |
| Explain issues and name the guideline or source | ✅ | `engine/pipeline.py` |
| Suggest corrections without overriding humans | ✅ | `engine/suggest.py`, `workflow.py` |
| Comments, approvals, revision history, roles | ✅ | `workflow.py`, `security.py` |
| Recurring problems and unclear guidelines | ✅ | `insights.py` |
| Protect confidential material, disclose AI use | ✅ | `security.py`, `engine/llm.py`, `audit.py` |
| Balance automation and human control | ✅ | `engine/pipeline.py`, `workflow.py` |
| Reliable, explainable results | ✅ | deterministic engine, a measured benchmark and 88 tests |

</details>

---

## 🧠 What's new in Round 3

| | Improvement | What you get |
|---|---|---|
| 🎯 | **Hybrid claim checking** | Adds a meaning layer on top of exact matching: a concept lexicon (optional sentence embeddings) and an *implied-claim finder* for lines like "never goes down" or "trusted by millions". An optional **cited AI judge** only counts when it names a real approved fact and quotes words that appear in it. A manager can switch hybrid on or off in **Settings**. |
| 📏 | **Accuracy Lab** | A 174-sentence labelled benchmark, one command (`make benchmark`) and a page (`#/accuracy`) with precision, recall, F1, false alarms and every sentence it got wrong. |
| 🔔 | **Alerts that reach people** | Email, Slack and signed webhooks (`X-CP-Signature`), per-person channel settings, retries, a weekly digest and a background scan, all visible in **Settings**. |
| 🗄 | **Production basics** | PostgreSQL support (`CP_DATABASE_URL`), versioned migrations, AES-256-GCM encrypted uploads and encrypted stored secrets. |
| 📑 | **Documents, not just text** | PDF page view with problems outlined, OCR for scanned PDFs, **Download corrected file** for Word and PowerPoint (formatting kept, changes it could not place are listed), and a logo check on images. |
| 🆓 | **AI judge without paying** | Works with Claude, or any OpenAI-compatible endpoint: Gemini's free key, Groq's free tier, or Ollama on your own computer. |

### 📏 Measured results (Accuracy Lab, 174 sentences, 10 approved facts)

| Mode | Exact match | Precision | Recall | F1 | False alarms | Missed problems |
|---|---|---|---|---|---|---|
| Rules only (Round 2) | 116/174 (67%) | 0.94 | 0.57 | 0.71 | 0/40 | 52/134 |
| **Hybrid (meaning layer)** | **153/174 (88%)** | **0.96** | **0.84** | **0.90** | 0/40 | 16/134 |
| Hybrid + cited AI judge | run `make benchmark` with an AI key to measure | | | | | |

The gain comes mostly from implied claims. Hybrid is **worse** on unsourced numbers (83% to 75%). The labels were written by the team, for one demo brand, in English, so these numbers describe this set and not real-world accuracy. Details and the full list of misses: **[docs/ACCURACY.md](docs/ACCURACY.md)**.

---

## 🔄 How it works

```mermaid
flowchart LR
  A([✍️ Write or upload]) --> B[🔎 Find claims]
  B --> C[📚 Check approved facts]
  C --> D[🧪 Run rule checks]
  D --> E[💬 Explain and suggest fixes]
  E --> F{👤 A person decides}
  F -->|approve| G[🚀 Publish with Claim Passports]
  F -->|needs changes| A
  G --> H[(🗂 Brand Vault)]
  H -. a source changes .-> I[⚠️ Affected pages flagged]
  I --> J[🛠 Suggested fix]
  J --> F
```

<div align="center"><img src="docs/assets/workflow.png" alt="Step by step workflow" width="92%"></div>

### 🐕 When a source changes

```mermaid
sequenceDiagram
  actor M as Manager
  participant V as Brand Vault
  participant W as Watcher
  actor O as Page owner
  M->>V: Change price from Rs. 449 to Rs. 499
  V->>W: Fact saved as version 2
  W->>W: Find passports made with version 1
  W-->>O: Alert and a suggested fix
  O->>O: Review and apply as a new draft
  O->>M: Submit for review again
```

<div align="center"><img src="docs/assets/source-watcher.png" alt="Source change watcher" width="92%"></div>

### 🚦 Passport status

| Status | Meaning |
|---|---|
| 🟢 **Valid** | Source unchanged and not close to expiry |
| 🟡 **Expiring soon** | Source expires within 14 days (`CP_EXPIRY_WARN_DAYS`) |
| 🔴 **Source changed** | The fact's wording or value changed after publishing |
| 🔴 **Source expired** | The expiry date has passed |
| 🟣 **No source** | A person approved the claim without a verified source |

> **Truth Debt** = (source changed + expired + removed + no source) ÷ all live claims.

---

## 🚀 Quick start

> **You need:** Python 3.10+ (tested on 3.12 and 3.13). Optional programs: `poppler` (PDF page view) and `tesseract` (OCR for images and scanned PDFs). macOS: `brew install poppler tesseract`; Ubuntu: `sudo apt install poppler-utils tesseract-ocr`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**. The first start loads a demo brand (*Lumio Invoice*), demo users and sample content.

### 🔑 Demo accounts  <sub>(password `demo1234`, change or disable before real use)</sub>

| Role | Email | Try this |
|---|---|---|
| 👑 Admin | `admin@demo.cp` | Everything, including users and audit |
| 🧭 Manager | `anil@demo.cp` | Edit the Vault, publish, watch Truth Debt and insights |
| 🕵️ Reviewer | `meera@demo.cp` | Approve content, including locked claims |
| ✍️ Creator | `priya@demo.cp` · `rohan@demo.cp` · `kabir@demo.cp` | Write content and decide on findings |

### 🧭 5-minute tour

0. **Anil** → *Accuracy Lab* → **Run benchmark now**: see rules-only vs hybrid. Then *Settings* for alerts and the scan.
1. **Priya** → *Content → Landing page*: read the findings, press **Fix easy ones**, or `j` / `a` with the keyboard.
2. **Anil** → *Dashboard*: the **Pricing page** shows *Source changed* and a fix waits under **Alerts**.
3. **Anil** → *Brand Vault*: edit a price and watch Truth Debt and Alerts update (or run `python scripts/demo_source_change.py`).
4. **Anil** → *Insights*: see which guideline is probably unclear.
5. **Anil** → *Proof Time Machine*: click an event on the timeline.

Full script: **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**.

<details>
<summary><b>🏢 Real install (no demo data)</b></summary>

```bash
CP_SEED_DEMO=0 \
CP_ADMIN_EMAIL=you@company.com \
CP_ADMIN_PASSWORD='a-long-password' \
CP_SECRET_KEY='a-long-random-string' \
python run.py
```
</details>

<details>
<summary><b>🐳 Docker</b></summary>

```bash
docker compose up --build      # http://localhost:8000
```
Add `--profile pg` and set `CP_DATABASE_URL=postgresql://cp:cp@db:5432/claimpassport` to use PostgreSQL. The Dockerfile installs `poppler` and `tesseract`. **The Docker build has not been run by the authors yet**; please test it on your machine.
</details>

<details>
<summary><b>🧪 Run the tests</b></summary>

```bash
python -m unittest discover -s tests -t . -v     # 88 unit and API tests
make benchmark                                   # accuracy on the labelled set
python tests/ui_smoke.py                         # optional: full journey in a real browser (needs playwright)
```
</details>

---

## 👥 Who can do what

| Action | ✍️ Creator | 🕵️ Reviewer | 🧭 Manager | 👑 Admin |
|---|:---:|:---:|:---:|:---:|
| See all content (creators see only their own) | ❌ | ✅ | ✅ | ✅ |
| Create content, accept or edit a suggestion | ✅ | ✅ | ✅ | ✅ |
| Keep a locked or high-risk wording as written | ❌ | ✅ | ✅ | ✅ |
| Approve content (never your own) | ❌ | ✅ | ✅ | ✅ |
| Approve content with locked claims | ❌ | ✅ | ❌ | ✅ |
| Publish | ❌ | ❌ | ✅ | ✅ |
| Edit the Brand Vault, run the watcher | ❌ | ❌ | ✅ | ✅ |
| See insights | ❌ | ✅ | ✅ | ✅ |
| See audit trail and AI log, list users | ❌ | ❌ | ✅ | ✅ |
| Create users | ❌ | ❌ | ❌ | ✅ |

### 🛡 Human-control rules (enforced in code and covered by tests)

- Nothing is applied until a person accepts it.
- Rejecting a finding needs a written reason.
- You cannot approve your own content.
- Approval is blocked while findings that need a person are open.
- Source changes only create **suggestions**, never edits.

---

## 📊 By the numbers

<table>
<tr>
<td width="50%"><img src="docs/assets/checks-by-area.png" alt="Checks by area"></td>
<td width="50%"><img src="docs/assets/tests-by-module.png" alt="Tests by module"></td>
</tr>
</table>

| 🐍 Python | 🟨 JavaScript | 🧪 Tests | 🔌 API endpoints | 📚 Docs |
|:---:|:---:|:---:|:---:|:---:|
| ~5,100 lines | ~1,100 lines | 88 passing | 67 | 8 guides |

---

## 🏗 Architecture

```mermaid
flowchart TB
  UI["🖥 Web app<br/>plain JavaScript"] --> API["🔌 Flask API"]
  API --> WF["🔁 Workflow"]
  API --> VT["📚 Brand Vault"]
  API --> PP["🛂 Passports and watcher"]
  API --> IN["📊 Insights"]
  WF --> EN["⚙️ Review engine"]
  EN --> ING["📄 File readers"]
  EN --> VER["✅ Fact checker"]
  EN --> CHK["🧪 Rule checkers"]
  EN --> SEM["🎯 Meaning layer<br/>lexicon, optional embeddings"]
  EN -. optional .-> LLM["🤖 AI judge and rewrites<br/>Claude or free provider"]
  API --> NT["🔔 Notifier and scheduler"]
  API --> PV["📑 PDF view, export, logo check"]
  NT --> CH["📧 Email · Slack · Webhook"]
  WF --> DB[("🗄 SQLite or PostgreSQL")]
  VT --> DB
  PP --> DB
  IN --> DB
```

<div align="center"><img src="docs/assets/tech-stack.png" alt="Technology stack" width="92%"></div>

<details>
<summary><b>🗂 Project layout</b></summary>

```text
claimpassport/
├── api.py            HTTP routes (Flask), kept thin
├── workflow.py       drafts, versions, decisions, review, publish, comments, diff
├── vault.py          facts, rules, guideline importer, glossary, assets
├── passports.py      claim passports, Truth Debt, half-life, Truth Feed, proof, timeline
├── watcher.py        source-change and expiry watcher, suggested fixes
├── insights.py       dashboard numbers, repeated mistakes, guideline gaps, trend
├── ingest.py         file readers (txt, md, html, pdf, docx, pptx, images + OCR)
├── security.py       passwords, tokens, roles, personal-data masking
├── audit.py          audit trail and AI transparency log
├── db.py, migrations.py, seed.py   SQLite and PostgreSQL layer, versioned schema, demo data
├── crypto.py, storage.py, settings.py   encryption, encrypted uploads, stored settings and secrets
├── notifier.py, scheduler.py   email/Slack/webhook alerts, digest, background scan
├── accuracy.py       labelled benchmark and `make benchmark`
├── pdfview.py, export.py, logo.py   PDF page view and OCR, corrected Word/PowerPoint, logo check
└── engine/
    ├── claims.py     find sentences that make claims
    ├── verify.py     match claims to approved facts
    ├── checkers.py   tone, terms, accessibility, visual, messaging
    ├── suggest.py    small, meaning-preserving fixes
    ├── semantic.py   meaning layer: concept lexicon, optional embeddings, implied claims
    ├── judge.py      cited AI judge (answer counts only with a real fact id and quote)
    ├── pipeline.py   reasons, sources, confidence, locks
    └── llm.py        optional AI helper: Claude or any OpenAI-compatible endpoint (off by default)
frontend/             single-page app (ES modules, no build step)
├── index.html, styles.css
└── js/               util, charts, art, app shell, pages/
data/sample/          demo guidelines, facts, glossary, sample files
data/accuracy/        the 174-sentence labelled benchmark
docs/                 guides, screenshots, diagrams
tests/                unit, API and optional browser tests
scripts/              sample file generator, demo helper
```
</details>

### 📥 What happens to one file

<div align="center"><img src="docs/assets/file-journey.png" alt="File journey" width="92%"></div>

---

## 🔒 Privacy and AI

- **Checks run inside your server.** Nothing is sent anywhere by default.
- The AI helper is **off** unless a provider is configured (`ANTHROPIC_API_KEY`, or `CP_LLM_PROVIDER=openai` with a free endpoint). It suggests rewrites and gives a cited second opinion, and a person always decides.
- Uploaded files are stored **encrypted** (AES-256-GCM); Slack and webhook addresses are stored encrypted.
- Before any AI call, personal data is **masked** and **confidential facts are withheld**.
- Every AI or outside-service call is written to the **AI Transparency log**.

<div align="center"><img src="docs/assets/privacy-flow.png" alt="Privacy flow" width="92%"></div>

More: **[docs/PRIVACY_AND_AI.md](docs/PRIVACY_AND_AI.md)**.

---

## 🔌 API in 30 seconds

```bash
# 1. sign in
TOKEN=$(curl -s localhost:5000/api/login -H 'Content-Type: application/json' \
  -d '{"email":"priya@demo.cp","password":"demo1234"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 2. check some text
curl -s localhost:5000/api/contents -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"API test","text":"Plans start at Rs. 599 per month!!"}'

# 3. the public Truth Feed (no login)
curl -s localhost:5000/.well-known/claims.json
```

Full list of endpoints: **[docs/API.md](docs/API.md)**.

<details>
<summary><b>⚙️ Configuration (environment variables)</b></summary>

| Variable | Default | Purpose |
|---|---|---|
| `CP_SECRET_KEY` | dev value | Signs login tokens. **Change it.** |
| `CP_SEED_DEMO` | `1` | Load demo brand, users and content on first start |
| `CP_ADMIN_EMAIL`, `CP_ADMIN_PASSWORD` | `admin@example.com`, `change-me-now` | First admin when demo data is off |
| `CP_DB_PATH`, `CP_UPLOAD_DIR` | `data/...` | Where the database and uploaded files live |
| `CP_EXPIRY_WARN_DAYS` | `14` | When a passport turns "expiring soon" |
| `CP_MAX_UPLOAD_MB` | `10` | Upload size limit |
| `ANTHROPIC_API_KEY`, `CP_USE_LLM` | empty | Optional AI helper with Claude |
| `CP_LLM_PROVIDER`, `CP_LLM_BASE_URL`, `CP_LLM_MODEL`, `CP_LLM_API_KEY` | `anthropic`, empty | Use any OpenAI-compatible endpoint instead (Gemini free key, Groq, Ollama) |
| `CP_DATABASE_URL` | empty | PostgreSQL URL; empty = the SQLite file |
| `CP_ENCRYPTION_KEY` | derived from secret | Key for encrypted uploads. **Back it up.** |
| `CP_HYBRID` | `0` | Hybrid claim checking on by default (managers can toggle in Settings) |
| `CP_SMTP_*`, `CP_PUBLIC_URL` | empty | Email alerts and links inside them |
| `CP_SLACK_WEBHOOK_URL`, `CP_WEBHOOK_URL`, `CP_WEBHOOK_SECRET` | empty | Slack and signed webhook alerts (admins can also set them in Settings) |
| `CP_SCHEDULER`, `CP_SCAN_INTERVAL_HOURS`, `CP_DIGEST_WEEKDAY` | `1`, `24`, `0` | Background scan and weekly digest |

See [.env.example](.env.example).
</details>

---

## ⚠️ Honest limits

> [!WARNING]
> This is a **working prototype**. Please read this before relying on it.

**Built and tested in the build environment:** hybrid checking, the Accuracy Lab, alerts (against local mail and web servers), the scheduler, migrations, encrypted uploads, PDF page view, corrected Word/PowerPoint export, the logo check, and the free-provider path (against a local fake server). 88 tests pass on SQLite and on PostgreSQL 16.

**Written but not yet verified by the authors:**
- 🤖 **AI judge with a real model.** Only the checks on its answers and a fake server were tested. Run `make benchmark` with your key to measure it.
- 🧬 **Embeddings.** The package is optional and was not installed, so only the concept lexicon was measured.
- 🐘 **Production PostgreSQL driver (`psycopg`).** The SQL ran on real PostgreSQL through a test stand-in, not through `psycopg`.
- 🐳 **Docker build and the GitHub Actions file.**
- 📧 **Real email and Slack.** Delivery was tested against local servers only.
- 🌐 **Browsers other than Chromium** (Safari, Firefox).

**Known gaps:**
- 📏 The benchmark is small, one brand, English, and labelled by the team. Hybrid is worse on unsourced numbers.
- 🎨 The logo check covers images only, not slides or PDF pages. No Word/PowerPoint styling checks.
- 📎 Corrected export covers .docx and .pptx; changes that cross paragraphs or table cells are listed, not applied.
- 🔍 Without embeddings, meaning matching uses a hand-made concept lexicon, so unusual wording can still be missed. Unsure results go to a person.
- 🔐 Passwords are hashed and logins use signed tokens. Change the demo passwords and secret key. There is no per-user SSO.

---

## 🗺 Roadmap

- [x] Brand Vault, rule engine, claim checker, 19 checks
- [x] Review workflow with roles, versions, diff, comments, audit trail
- [x] Claim Passports, source-change watcher, Truth Debt, half-life
- [x] Truth Feed, Proof Time Machine, insights, AI Transparency log
- [x] Interactive UI with charts, dark mode and command palette
- [x] PostgreSQL support and versioned migrations (driver path still to verify)
- [x] Hybrid checking, implied claims, cited AI judge, Accuracy Lab
- [x] Email, Slack and webhook alerts, weekly digest, background scan
- [x] PDF page view, OCR for scanned PDFs, corrected Word/PowerPoint export, logo check on images
- [x] Encrypted uploads and secrets
- [ ] Verify embeddings, the AI judge and Docker on real infrastructure
- [ ] FastAPI port (only `api.py` needs to change)
- [ ] Logo and layout checks for slides and PDF pages
- [ ] A larger, multi-brand benchmark labelled by people outside the team
- [ ] Browser extension to check AI-written content before posting

Details and suggested next tasks: **[docs/ROADMAP.md](docs/ROADMAP.md)**.

---

## ☁️ Deploy

Short version (full steps in **[docs/DEPLOY.md](docs/DEPLOY.md)**):

1. Push the repo to GitHub.
2. On Render, create a **Web Service** from the repo. Build: `pip install -r requirements.txt`. Start: `gunicorn -w 1 --threads 4 run:app`. Keep **one** worker so the background scheduler runs once.
3. Set `CP_SECRET_KEY`, `CP_ENCRYPTION_KEY`, `CP_PUBLIC_URL` and, if you want the AI judge, the `CP_LLM_*` variables (free Gemini key) or `ANTHROPIC_API_KEY`.
4. Open `/api/health`, sign in, check **Settings** and **Accuracy Lab**.

On a free plan the disk is temporary, so data resets on redeploy. Use PostgreSQL or a persistent disk for real data. PDF page view and OCR need `poppler` and `tesseract`, which come with the Docker runtime.

---

## 📖 Documentation

| Guide | What is inside |
|---|---|
| 🏗 [ARCHITECTURE](docs/ARCHITECTURE.md) | How one review works, data model, design decisions |
| 🔌 [API](docs/API.md) | Every endpoint with roles |
| 📝 [GUIDELINE_FORMAT](docs/GUIDELINE_FORMAT.md) | Write guidelines the platform can read |
| 🎬 [DEMO_SCRIPT](docs/DEMO_SCRIPT.md) | A 6-minute demo, step by step |
| 🔒 [PRIVACY_AND_AI](docs/PRIVACY_AND_AI.md) | What is sent where, and what is not |
| 📏 [ACCURACY](docs/ACCURACY.md) | Measured benchmark results and how to read them |
| ☁️ [DEPLOY](docs/DEPLOY.md) | Run locally, push to GitHub, deploy on Render, free AI provider setup |
| 🗺 [ROADMAP](docs/ROADMAP.md) | Next tasks and a quality checklist |

---

## 👩‍💻 Team Synqora

| | Name | Focus |
|---|---|---|
| 🧠 | **Luv Malik** (team leader) | AI and detection: claim finding, fact checking, fixes, confidence |
| 🧱 | **Aditi Singh** | Platform and security: database, workflow, watcher, transparency log |
| 🎨 | **Aanya Gupta** | Frontend, insights and demo: screens, dashboard, presentation |

Built for the **Inkloom AI** problem statement. Parts of the code and documents were drafted with help from an AI assistant (Claude by Anthropic). Please review everything before relying on it.

## 📄 License

MIT. See [LICENSE](LICENSE).

<div align="center"><sub>Made with ❤️ by Team Synqora · Keep every claim true.</sub></div>
