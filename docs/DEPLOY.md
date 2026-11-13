# Deploy guide: Claim Passport

## 0. Where settings live
The app reads **environment variables only** (it does not read a `.env` file by itself). Names are in `claimpassport/config.py` and `.env.example`.
The Anthropic key is the variable **`ANTHROPIC_API_KEY`** (model: `CP_LLM_MODEL`, default `claude-sonnet-5-5`). Never put the key in a source file or commit it.

| Where you run | How to set the key |
|---|---|
| Your laptop | `export ANTHROPIC_API_KEY=sk-ant-...` (or `set -a; source .env; set +a` first) |
| docker compose | put `ANTHROPIC_API_KEY=...` in a file named `.env` next to `docker-compose.yml`; compose passes it in |
| Render / Railway / Fly | add it in the platform's Environment / Variables / Secrets screen |

Get a key at console.anthropic.com > API keys. Without a key the app still works; the AI judge and AI rewrite ideas are simply off.

## 1. Run it locally first
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -t .      (expect 84 tests, all OK)
export ANTHROPIC_API_KEY=sk-ant-...             # optional
python run.py                                   # http://127.0.0.1:5000  (demo logins shown on the sign-in page)
make benchmark                                  # measures accuracy; add the key to include the AI judge row
```
PDF page view needs `poppler-utils`; scanned-PDF OCR needs `tesseract-ocr` (macOS: `brew install poppler tesseract`; Ubuntu: `sudo apt install poppler-utils tesseract-ocr`).

## 2. Put the code on GitHub
```
unzip claim-passport-updated.zip && cd claim-passport
git init -b main
git status                       # confirm .env, *.db, data/uploads are NOT listed (they are in .gitignore)
git add -A
git commit -m "Round 3: hybrid verification, alerts, Postgres, PDF view, export, logo check"
# create an EMPTY repo on github.com (no README), then:
git remote add origin https://github.com/<your-user>/<repo>.git
git push -u origin main
```
If you already have a repo: clone it, copy these files over it, then `git add -A && git commit && git push`.
If push asks for a password, use a Personal Access Token (GitHub > Settings > Developer settings) or `gh auth login`.

## 3. Deploy (recommended: Docker on Render, with PostgreSQL)
Why not plain SQLite on a free host: those disks reset on restart, so you would lose data and uploads. Use Postgres, plus a persistent disk for uploads.

1. Render.com > New > **PostgreSQL**. Copy its *Internal Database URL*.
2. Render > New > **Web Service** > connect your GitHub repo > Runtime **Docker** (it uses the `Dockerfile`).
3. Add a **Disk** mounted at `/data` (uploads are stored in `/data/uploads`).
4. Environment variables:
   - `CP_DATABASE_URL` = the Postgres URL (starts with `postgresql://`)
   - `CP_SECRET_KEY` = long random string (`python -c "import secrets;print(secrets.token_urlsafe(48))"`)
   - `CP_ENCRYPTION_KEY` = another long random string. **Back it up: if lost, uploaded files cannot be decrypted.**
   - `ANTHROPIC_API_KEY` = your key
   - `CP_SEED_DEMO` = `0` for a real install, then also `CP_ADMIN_EMAIL` and `CP_ADMIN_PASSWORD` (first admin). Use `1` only for a demo.
   - `CP_PUBLIC_URL` = your site's https address (used in alert links)
   - Optional email: `CP_SMTP_HOST`, `CP_SMTP_PORT`, `CP_SMTP_USER`, `CP_SMTP_PASSWORD`, `CP_SMTP_FROM`
5. Deploy. Open `https://<service>.onrender.com/api/health` (should answer OK), then sign in.
6. Settings page: add the Slack/webhook address (admin), press "Send test alert to me", check the scheduler "Run now".

Other hosts work the same way (Railway, Fly.io, a VPS): Docker image + Postgres + a persistent volume at `/data`. On a VPS: install Docker, put a `.env` beside `docker-compose.yml`, run `docker compose up -d --build` (add `--profile pg` and set `CP_DATABASE_URL=postgresql://cp:cp@db:5432/claimpassport` for Postgres), and put Caddy or nginx in front for HTTPS.

## 4. Before real users
- Change every default secret; set `CP_SEED_DEMO=0`.
- Keep ONE web worker (the Dockerfile does) so the background scheduler runs once.
- HTTPS only. Back up the database and `/data/uploads` together with `CP_ENCRYPTION_KEY`.
- The code is verified on SQLite and PostgreSQL 16 through a test stand-in; the production `psycopg` driver, the Docker build and real email/Slack are **not yet verified**. Check them on a staging copy first.
