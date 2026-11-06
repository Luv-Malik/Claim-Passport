# Roadmap and how to improve it

## Near term (good first tasks)

| Task | Why | Where |
|---|---|---|
| PostgreSQL support | multi-user and larger data. The SQL is standard; replace `db.py` with a connection pool and add migrations (Alembic) | `db.py` |
| Embedding search instead of TF-IDF | better matching for unusual wording. Keep the same `FactIndex.search` interface | `engine/verify.py` |
| Move the API to FastAPI | typed models, automatic docs. Only `api.py` needs rewriting | `api.py` |
| Email and Slack alerts | alerts are in-app only today | `watcher.notify` |
| Scheduled expiry scan | run `watcher.scan_expiry` daily (cron or a background worker) | `watcher.py` |
| OCR for scanned PDFs | render pages to images, then run the existing image OCR | `ingest.py` |
| Write fixes back into Word and PowerPoint files | today fixes apply to extracted text | `ingest.py`, `workflow.py` |
| Logo and layout checks for images | detect logo placement and clear space | `engine/checkers.py` |
| Encrypted storage of uploads | uploads are stored as plain files | `api.save_upload` |
| Browser extension / API key access | check AI-generated content before it is posted | `api.py` |

## Medium term

- Multi-brand and multi-language support (separate Vaults, language-aware tone checks).
- Learn from decisions: use accepted and rejected suggestions to rank future suggestions (the data is already stored in `findings`).
- Per-team approval chains and due dates for reviews.
- Connectors: CMS, Canva, Google Workspace, social schedulers.
- Watch live URLs and social posts for drift after publishing.
- Industry rule packs (finance, health, education).
- Public trust badge page for each published item.

## Suggested team split for the next phase

| Person | Focus |
|---|---|
| Luv Malik | Detection quality: embedding search, test set with labelled examples, accuracy measurement, AI helper with the live API |
| Aditi Singh | Platform: PostgreSQL, migrations, FastAPI port, background jobs, security hardening, encryption |
| Aanya Gupta | Product and UI: design polish, accessibility of the app itself, onboarding, demo and documentation |

## Quality checklist before using with real content

1. Replace demo users, passwords and `CP_SECRET_KEY`. Run with `CP_SEED_DEMO=0`.
2. Import your real guidelines and facts (with sources and owners).
3. Build a small set of real examples with the expected findings, and measure false positives and misses. Tune rules accordingly.
4. Test the optional AI helper with your own key and review the AI log.
5. Put the app behind HTTPS and a reverse proxy.
