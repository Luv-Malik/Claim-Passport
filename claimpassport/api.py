"""HTTP API (Flask). Routes are thin: the real logic lives in the other modules."""
import functools
import mimetypes
import time
from collections import defaultdict
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

from . import (__version__, accuracy, audit, clock, export, ingest, insights, logo, notifier, passports, pdfview,
               security, settings, storage, vault, watcher, workflow)
from .scheduler import Scheduler
from . import seed as seedmod
from .config import BASE_DIR, load_config
from .db import DB, jload
from .engine.llm import LLMClient
from .errors import AppError

PRIVILEGED = ("reviewer", "manager", "admin")


def create_app(overrides=None):
    cfg = load_config(overrides)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = cfg["MAX_UPLOAD_MB"] * 1024 * 1024
    db = DB(cfg["DATABASE_URL"] or cfg["DB_PATH"], cfg.get("DB_DRIVER"))
    db.init()
    vault.ensure_builtin_rules(db)
    if not db.one("SELECT id FROM users LIMIT 1"):
        if cfg["SEED_DEMO"]:
            seedmod.seed_demo(db, cfg)
        else:
            seedmod.bootstrap_admin(db)
    llm = LLMClient(cfg)
    scheduler = Scheduler(db, cfg, sync=bool(cfg.get("SCHEDULER_SYNC")))
    if cfg["SCHEDULER"] and not cfg.get("SCHEDULER_SYNC"):
        scheduler.start()
    app.cp_db, app.cp_cfg, app.cp_scheduler = db, cfg, scheduler
    failures = defaultdict(list)          # tiny login throttle: 10 failures per 5 minutes per address

    # ------------------------------------------------------------ helpers
    def current_user():
        h = request.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            return None
        claims = security.read_token(h[7:], cfg["SECRET_KEY"])
        if not claims:
            return None
        return db.one("SELECT id, name, email, role, team FROM users WHERE id=?", (int(claims["sub"]),))

    def need(action=None):
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*a, **kw):
                u = current_user()
                if not u:
                    return jsonify(error="Please sign in."), 401
                if action and not security.can(u["role"], action):
                    return jsonify(error="Your role does not allow this action."), 403
                g.user = u
                return fn(*a, **kw)
            return wrapper
        return deco

    def body():
        return request.get_json(silent=True) or {}

    def visible_content(cid):
        c = workflow.get_content(db, cid)
        if not workflow.visible_to(c, g.user):
            raise AppError("Content not found.", 404)
        return c

    def out_finding(f):
        d = dict(f)
        if isinstance(d.get("suggestions"), str):
            d["suggestions"] = jload(d["suggestions"], [])
        if d.get("source_confidential") and g.user["role"] not in PRIVILEGED:
            d["source_ref"] = "Confidential source (reference hidden)"
        return d

    def out_fact(f):
        d = dict(f)
        if d["confidential"] and g.user["role"] not in PRIVILEGED:
            d.update(statement="(confidential fact)", value="(confidential)", source_doc="(hidden)", source_ref="")
        return d

    def save_upload(filename, data):
        return storage.save_upload(cfg, filename, data)        # encrypted at rest

    # ------------------------------------------------------------ errors and headers
    @app.errorhandler(AppError)
    def on_app_error(e):
        return jsonify(error=str(e), **e.extra), e.status

    @app.errorhandler(404)
    def on_404(_):
        return jsonify(error="Not found."), 404

    @app.errorhandler(405)
    def on_405(_):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(413)
    def on_413(_):
        return jsonify(error=f"File too large (limit {cfg['MAX_UPLOAD_MB']} MB)."), 413

    @app.errorhandler(Exception)
    def on_error(e):
        app.logger.exception("Unhandled error")
        return jsonify(error="Something went wrong on the server."), 500

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                   "img-src 'self' data:; script-src 'self'; frame-ancestors 'none'")
        return resp

    # ------------------------------------------------------------ public
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version=__version__)

    @app.get("/api/meta")
    def meta():
        demo = bool(db.one("SELECT id FROM users WHERE email='admin@demo.cp'"))
        return jsonify(version=__version__, demo_login=demo, llm_enabled=llm.available, llm_model=llm.model if llm.available else None,
                       roles=list(security.ROLES), today=clock.today().isoformat(), categories=list(vault.CATEGORIES),
                       database=db.kind, hybrid=settings.hybrid_enabled(db, cfg),
                       disclosure=("Checks run with a rules engine inside this server. An optional AI model may suggest rewrites; "
                                   "it never decides. People approve everything before it is published."))

    @app.get("/.well-known/claims.json")
    @app.get("/api/public/claims")
    def public_claims():
        return jsonify(passports.truth_feed(db, clock.today()))

    # ------------------------------------------------------------ auth
    @app.post("/api/login")
    def login():
        ip = request.remote_addr or "?"
        now = time.time()
        failures[ip] = [t for t in failures[ip] if now - t < 300]
        if len(failures[ip]) >= 10:
            return jsonify(error="Too many failed attempts. Please wait a few minutes."), 429
        b = body()
        u = db.one("SELECT * FROM users WHERE email=?", ((b.get("email") or "").strip().lower(),))
        if not u or not security.verify_password(b.get("password") or "", u["password_hash"]):
            failures[ip].append(now)
            return jsonify(error="Wrong email or password."), 401
        audit.log(db, u["name"], "login", "user", u["id"])
        return jsonify(token=security.make_token(u, cfg["SECRET_KEY"], cfg["TOKEN_HOURS"]),
                       user={k: u[k] for k in ("id", "name", "email", "role", "team")})

    @app.get("/api/me")
    @need()
    def me():
        return jsonify(user=g.user)

    @app.get("/api/users")
    @need("users")
    def users():
        return jsonify(users=db.q("SELECT id, name, email, role, team FROM users ORDER BY name"))

    @app.post("/api/users")
    @need("users_edit")
    def add_user():
        b = body()
        if b.get("role") not in security.ROLES or not (b.get("name") and b.get("email") and len(b.get("password") or "") >= 8):
            raise AppError("Name, email, a valid role and a password of at least 8 characters are required.")
        if db.one("SELECT id FROM users WHERE email=?", (b["email"].lower(),)):
            raise AppError("That email is already used.", 409)
        uid = seedmod.add_user(db, b["name"], b["email"], b["role"], b.get("team", ""), b["password"])
        audit.log(db, g.user["name"], "user.create", "user", uid, {"role": b["role"]})
        return jsonify(id=uid), 201

    # ------------------------------------------------------------ vault
    @app.get("/api/vault/summary")
    @need()
    def vault_summary():
        return jsonify(facts=len(vault.list_facts(db)), rules=len(vault.list_rules(db)),
                       glossary=len(vault.list_glossary(db)), assets=len(vault.list_assets(db)),
                       guideline_docs=db.q("SELECT id, title, version, created_at FROM guideline_docs ORDER BY id DESC"))

    @app.get("/api/vault/facts")
    @need()
    def facts():
        today = clock.today()
        out = []
        for f in vault.list_facts(db):
            d = out_fact(f)
            exp = clock.parse_date(f["expires_on"])
            d["days_left"] = (exp - today).days if exp else None
            d["live_uses"] = db.one("SELECT COUNT(*) n FROM passports WHERE fact_id=? AND active=1", (f["id"],))["n"]
            out.append(d)
        return jsonify(facts=out)

    @app.post("/api/vault/facts")
    @need("vault_edit")
    def fact_create():
        return jsonify(fact=vault.create_fact(db, body(), g.user)), 201

    @app.put("/api/vault/facts/<int:fid>")
    @need("vault_edit")
    def fact_update(fid):
        b = body()
        before, after = vault.update_fact(db, fid, b, g.user, b.get("note", ""))
        proposals = watcher.on_fact_changed(db, before, after, g.user)
        if after["version"] > before["version"]:
            scheduler.kick("fact_change")        # alerts go out right away, without slowing this request
        return jsonify(fact=after, version_changed=after["version"] > before["version"], proposals_created=len(proposals))

    @app.get("/api/vault/facts/<int:fid>/history")
    @need("insights")
    def fact_history(fid):
        return jsonify(history=vault.fact_history(db, fid))

    @app.get("/api/vault/rules")
    @need()
    def rules():
        return jsonify(rules=vault.list_rules(db))

    @app.put("/api/vault/rules/<code>")
    @need("vault_edit")
    def rule_update(code):
        return jsonify(rule=vault.update_rule(db, code, body(), g.user))

    @app.post("/api/vault/guidelines/import")
    @need("vault_edit")
    def guidelines_import():
        b = body()
        return jsonify(vault.import_guidelines(db, b.get("markdown") or "", b.get("title"), b.get("version"), g.user))

    @app.get("/api/vault/glossary")
    @need()
    def glossary():
        return jsonify(glossary=vault.list_glossary(db))

    @app.post("/api/vault/glossary")
    @need("vault_edit")
    def glossary_add():
        return jsonify(id=vault.add_glossary(db, body(), g.user)), 201

    @app.delete("/api/vault/glossary/<int:gid>")
    @need("vault_edit")
    def glossary_delete(gid):
        vault.delete_glossary(db, gid, g.user)
        return jsonify(ok=True)

    @app.get("/api/vault/assets")
    @need()
    def assets():
        out = vault.list_assets(db)
        for a in out:
            if a["name"] == "logo" and isinstance(a["value"], dict):       # never send the image data in a list
                a["value"] = {k: v for k, v in a["value"].items() if k != "png_b64"} | {"has_image": bool(a["value"].get("png_b64"))}
        return jsonify(assets=out)

    @app.put("/api/vault/assets/<name>")
    @need("vault_edit")
    def asset_set(name):
        b = body()
        if "value" not in b:
            raise AppError("Missing value.")
        vault.set_asset(db, name, b["value"], g.user, notes=b.get("notes", ""))
        return jsonify(ok=True)

    # ------------------------------------------------------------ content
    @app.get("/api/contents")
    @need()
    def contents():
        rows = db.q("SELECT c.id, c.title, c.fmt, c.status, c.channel, c.current_version, c.updated_at, c.needs_refresh, "
                    "c.owner_id, u.name AS owner_name, u.team AS owner_team FROM contents c JOIN users u ON u.id=c.owner_id "
                    "ORDER BY c.updated_at DESC, c.id DESC")
        status, q = request.args.get("status"), (request.args.get("q") or "").lower()
        out = []
        for r in rows:
            if g.user["role"] == "creator" and r["owner_id"] != g.user["id"]:
                continue
            if status and r["status"] != status:
                continue
            if q and q not in r["title"].lower():
                continue
            v = db.one("SELECT analysis FROM content_versions WHERE content_id=? AND version=?", (r["id"], r["current_version"]))
            summ = (jload(v["analysis"], {}) or {}).get("summary", {})
            r["score"] = summ.get("score")
            r["open_findings"] = db.one("SELECT COUNT(*) n FROM findings WHERE content_id=? AND version=? AND decision='open'",
                                        (r["id"], r["current_version"]))["n"]
            out.append(r)
        return jsonify(contents=out)

    @app.post("/api/contents")
    @need("create_content")
    def content_create():
        f = request.files.get("file")
        if f and f.filename:
            data = f.read()
            if not data:
                raise AppError("The file is empty.")
            r = ingest.extract(f.filename, data)
            stored = save_upload(f.filename, data)
            meta = r["meta"]
            if r["fmt"] == "image":
                meta["alt_text"] = (request.form.get("alt_text") or "").strip()
            meta["stored_as"] = stored
            title = (request.form.get("title") or Path(f.filename).stem).strip()
            cid = workflow.create_content(db, cfg, g.user, title, r["fmt"], r["text"], meta, request.form.get("channel") or "website",
                                          request.form.get("ai_assisted") in ("1", "true", "on"), f.filename, llm)
        else:
            b = body()
            fmt = b.get("fmt", "text")
            if fmt not in ("text", "markdown", "html"):
                raise AppError("For pasted text, format must be text, markdown or html.")
            cid = workflow.create_content(db, cfg, g.user, b.get("title"), fmt, b.get("text") or "", {}, b.get("channel") or "website",
                                          bool(b.get("ai_assisted")), "", llm)
        return jsonify(id=cid), 201

    @app.get("/api/contents/<int:cid>")
    @need()
    def content_detail(cid):
        c = visible_content(cid)
        v = workflow.current_version(db, c)
        names = {u["id"]: u["name"] for u in db.q("SELECT id, name FROM users")}
        findings = []
        for f in workflow.findings_for(db, cid, c["current_version"]):
            d = out_finding(f)
            d["decision_by_name"] = names.get(f["decision_by"])
            findings.append(d)
        meta = {k: val for k, val in v["meta"].items() if k not in ("page_spans", "stored_as")}
        pub = db.one("SELECT id, version, published_at FROM publications WHERE content_id=? AND active=1", (cid,))
        stored = v["meta"].get("stored_as")
        files = {"original": bool(stored), "page_view": c["fmt"] == "pdf" and bool(stored) and pdfview.tools_available()["poppler"],
                 "pages": v["meta"].get("pages"), "export": c["fmt"] in export.FORMATS and bool(stored),
                 "ocr_pages": v["meta"].get("ocr_pages") or []}
        return jsonify(
            content={**c, "editable": c["fmt"] in ingest.EDITABLE}, text=v["text"], meta=meta, files=files,
            summary=(v["analysis"] or {}).get("summary", {}), findings=findings,
            comments=workflow.list_comments(db, cid),
            versions=db.q("SELECT v.version, v.note, v.created_at, u.name AS author FROM content_versions v "
                          "LEFT JOIN users u ON u.id=v.created_by WHERE v.content_id=? ORDER BY v.version DESC", (cid,)),
            approvals=db.q("SELECT a.decision, a.note, a.version, a.created_at, u.name AS reviewer FROM approvals a "
                           "JOIN users u ON u.id=a.user_id WHERE a.content_id=? ORDER BY a.id DESC", (cid,)),
            actions=workflow.allowed_actions(db, c, g.user), publication=pub,
            passports=[{k: p[k] for k in ("id", "claim_text", "status", "color", "label", "fact_key", "days_left")}
                       for p in passports.list_passports(db, clock.today(), cfg["EXPIRY_WARN_DAYS"], content_id=cid)],
            proposals=[p for p in watcher.list_proposals(db, "open", g.user) if p["content_id"] == cid])

    @app.get("/api/contents/<int:cid>/text")
    @need()
    def content_text(cid):
        c = visible_content(cid)
        ver = request.args.get("version", type=int) or c["current_version"]
        row = db.one("SELECT text FROM content_versions WHERE content_id=? AND version=?", (cid, ver))
        if not row:
            raise AppError("Version not found.", 404)
        return row["text"], 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.post("/api/contents/<int:cid>/versions")
    @need()
    def content_new_version(cid):
        visible_content(cid)
        b = body()
        nv = workflow.add_version(db, cfg, g.user, cid, b.get("text") or "", b.get("note", ""), llm)
        return jsonify(version=nv), 201

    @app.post("/api/contents/<int:cid>/alt-text")
    @need()
    def content_alt_text(cid):
        c = visible_content(cid)
        if c["fmt"] != "image":
            raise AppError("Alt text can be added to image uploads only.")
        cur = workflow.current_version(db, c)
        nv = workflow.add_version(db, cfg, g.user, cid, cur["text"], "Added alt text", llm, {"alt_text": (body().get("alt_text") or "").strip()})
        return jsonify(version=nv), 201

    @app.post("/api/contents/<int:cid>/analyze")
    @need()
    def content_analyze(cid):
        c = visible_content(cid)
        workflow.run_analysis(db, cfg, cid, c["current_version"], llm)
        return jsonify(ok=True)

    @app.post("/api/contents/<int:cid>/apply")
    @need()
    def content_apply(cid):
        visible_content(cid)
        nv, skipped = workflow.apply_decisions(db, cfg, g.user, cid, llm)
        return jsonify(version=nv, skipped=skipped)

    @app.get("/api/contents/<int:cid>/diff")
    @need()
    def content_diff(cid):
        c = visible_content(cid)
        return jsonify(workflow.diff(db, cid, request.args.get("from", type=int) or max(1, c["current_version"] - 1),
                                      request.args.get("to", type=int) or c["current_version"]))

    @app.post("/api/findings/<int:fid>/decision")
    @need("decide")
    def finding_decision(fid):
        b = body()
        f = workflow.decide(db, g.user, fid, b.get("decision"), b.get("reason", ""), b.get("suggestion_index"), b.get("final_text"))
        return jsonify(finding=out_finding({**f, "suggestions": jload(f["suggestions"], [])}))

    for name, fn in (("submit", lambda c, b: workflow.submit(db, g.user, c, b.get("note", ""))),
                     ("approve", lambda c, b: workflow.approve(db, g.user, c, b.get("note", ""))),
                     ("request-changes", lambda c, b: workflow.request_changes(db, g.user, c, b.get("note", ""))),
                     ("publish", lambda c, b: workflow.publish(db, cfg, g.user, c))):
        def make(fn=fn, name=name):
            @need()
            def route(cid):
                visible_content(cid)
                c = fn(cid, body())
                return jsonify(status=c["status"])
            route.__name__ = "content_" + name.replace("-", "_")
            return route
        app.add_url_rule(f"/api/contents/<int:cid>/{name}", view_func=make(), methods=["POST"])

    @app.get("/api/contents/<int:cid>/comments")
    @need()
    def comments_list(cid):
        visible_content(cid)
        return jsonify(comments=workflow.list_comments(db, cid))

    @app.post("/api/contents/<int:cid>/comments")
    @need()
    def comments_add(cid):
        visible_content(cid)
        b = body()
        a = [b.get("anchor_start"), b.get("anchor_end")] if b.get("anchor_start") is not None else None
        return jsonify(id=workflow.add_comment(db, g.user, cid, b.get("body", ""), a)), 201

    @app.get("/api/contents/<int:cid>/transparency")
    @need()
    def transparency(cid):
        visible_content(cid)
        return jsonify(events=db.q("SELECT * FROM ai_log WHERE content_id=? ORDER BY id DESC LIMIT 100", (cid,)),
                       llm_enabled=llm.available, ai_assisted=bool(workflow.get_content(db, cid)["ai_assisted"]))

    # ------------------------------------------------------------ passports, watcher, proof
    @app.get("/api/passports")
    @need()
    def passports_list():
        own = g.user["id"] if g.user["role"] == "creator" else None
        items = passports.list_passports(db, clock.today(), cfg["EXPIRY_WARN_DAYS"], status=request.args.get("status"), owner_id=own)
        for p in items:
            if p.get("confidential") and g.user["role"] not in PRIVILEGED:
                p.update(fact_statement="(confidential fact)", fact_value="(confidential)", source_doc="(hidden)", source_ref="")
        return jsonify(passports=items)

    @app.post("/api/watcher/run")
    @need("watcher")
    def watcher_run():
        return jsonify(new_alerts=watcher.scan_expiry(db, clock.today(), cfg["EXPIRY_WARN_DAYS"]))

    @app.get("/api/proposals")
    @need()
    def proposals():
        return jsonify(proposals=watcher.list_proposals(db, request.args.get("status", "open"), g.user))

    @app.post("/api/proposals/<int:pid>/apply")
    @need()
    def proposal_apply(pid):
        return jsonify(version=watcher.apply_proposal(db, cfg, g.user, pid, llm))

    @app.post("/api/proposals/<int:pid>/dismiss")
    @need()
    def proposal_dismiss(pid):
        watcher.dismiss_proposal(db, g.user, pid)
        return jsonify(ok=True)

    @app.get("/api/notifications")
    @need()
    def notifications():
        return jsonify(notifications=db.q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (g.user["id"],)))

    @app.post("/api/notifications/read")
    @need()
    def notifications_read():
        db.run("UPDATE notifications SET read=1 WHERE user_id=?", (g.user["id"],))
        return jsonify(ok=True)

    @app.get("/api/proof")
    @need()
    def proof():
        cid = request.args.get("content_id", type=int)
        if not cid:
            raise AppError("content_id is required.")
        visible_content(cid)
        res = passports.proof_at(db, cid, request.args.get("at") or clock.today().isoformat())
        if res is None:
            raise AppError("Please give the date as YYYY-MM-DD.")
        return jsonify(res)

    @app.get("/api/contents/<int:cid>/timeline")
    @need()
    def content_timeline(cid):
        visible_content(cid)
        return jsonify(events=passports.timeline(db, cid))

    # ------------------------------------------------------------ insights and audit
    @app.get("/api/insights/overview")
    @need()
    def i_overview():
        return jsonify(insights.overview(db, g.user, clock.today(), cfg["EXPIRY_WARN_DAYS"]))

    @app.get("/api/insights/mistakes")
    @need("insights")
    def i_mistakes():
        return jsonify(insights.mistakes(db))

    @app.get("/api/insights/guideline-gaps")
    @need("insights")
    def i_gaps():
        return jsonify(gaps=insights.guideline_gaps(db))

    @app.get("/api/insights/half-life")
    @need("insights")
    def i_half():
        return jsonify(items=passports.half_life(db, clock.today()))

    @app.get("/api/insights/trend")
    @need("insights")
    def i_trend():
        return jsonify(trend=insights.trend(db, 14, clock.today()))

    @app.get("/api/audit")
    @need("audit")
    def audit_view():
        return jsonify(audit=db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200"),
                       ai=db.q("SELECT * FROM ai_log ORDER BY id DESC LIMIT 100"))

    # ------------------------------------------------------------ original files, PDF page view, corrected export
    def original_bytes(c):
        v = workflow.current_version(db, c)
        data = storage.load_upload(cfg, v["meta"].get("stored_as"))
        if data is None:
            raise AppError("The original file is not available for this content.", 404)
        return v, data

    @app.get("/api/contents/<int:cid>/original")
    @need()
    def content_original(cid):
        c = visible_content(cid)
        _, data = original_bytes(c)
        name = (c["filename"] or f"content-{cid}").replace('"', "")
        return data, 200, {"Content-Type": mimetypes.guess_type(name)[0] or "application/octet-stream",
                           "Content-Disposition": f'attachment; filename="{name}"'}

    @app.get("/api/contents/<int:cid>/pages")
    @need()
    def pdf_pages(cid):
        c = visible_content(cid)
        if c["fmt"] != "pdf":
            raise AppError("Page view is for PDF files.", 400)
        v, data = original_bytes(c)
        v1 = db.one("SELECT text FROM content_versions WHERE content_id=? AND version=1", (cid,))
        located = pdfview.locate(workflow.findings_for(db, cid, c["current_version"]), v["text"], v1["text"], v["meta"].get("page_spans"))
        per_page = {}
        for loc in located.values():
            per_page[loc["page"]] = per_page.get(loc["page"], 0) + 1
        return jsonify(pages=pdfview.page_count(data), findings_per_page=per_page, ocr_pages=v["meta"].get("ocr_pages") or [],
                       tools=pdfview.tools_available())

    @app.get("/api/contents/<int:cid>/pages/<int:page>")
    @need()
    def pdf_page(cid, page):
        c = visible_content(cid)
        if c["fmt"] != "pdf":
            raise AppError("Page view is for PDF files.", 400)
        v, data = original_bytes(c)
        n = pdfview.page_count(data)
        if page < 1 or page > n:
            raise AppError("That page does not exist.", 404)
        v1 = db.one("SELECT text FROM content_versions WHERE content_id=? AND version=1", (cid,))
        findings = workflow.findings_for(db, cid, c["current_version"])
        located = pdfview.locate(findings, v["text"], v1["text"], v["meta"].get("page_spans"))
        try:
            res = pdfview.render_page(data, page, findings, located, page in (v["meta"].get("ocr_pages") or []))
        except RuntimeError as exc:
            raise AppError(str(exc), 501)
        res.update(pages=n, findings_here=sum(1 for loc in located.values() if loc["page"] == page))
        return jsonify(res)

    def export_for(cid):
        c = visible_content(cid)
        if c["fmt"] not in export.FORMATS:
            raise AppError("Corrected-file export works for Word (.docx) and PowerPoint (.pptx) files.", 415)
        v, data = original_bytes(c)
        blob, report = export.export_corrected(c["fmt"], data, v["text"])
        return c, blob, report

    @app.get("/api/contents/<int:cid>/export/report")
    @need()
    def export_report(cid):
        _, _, report = export_for(cid)
        return jsonify(report)

    @app.get("/api/contents/<int:cid>/export")
    @need()
    def export_file(cid):
        c, blob, report = export_for(cid)
        stem, ext = (c["filename"] or f"content-{cid}.{c['fmt']}").rsplit(".", 1) if "." in (c["filename"] or "") else (f"content-{cid}", c["fmt"])
        audit.log(db, g.user["name"], "content.export", "content", cid, {"applied": len(report["applied"]), "skipped": len(report["skipped"])})
        return blob, 200, {"Content-Type": export.FORMATS[c["fmt"]],
                           "Content-Disposition": f'attachment; filename="{stem.replace(chr(34), "")}-corrected.{ext}"',
                           "X-Export-Applied": str(len(report["applied"])), "X-Export-Skipped": str(len(report["skipped"]))}

    # ------------------------------------------------------------ brand logo (Vault asset)
    @app.post("/api/vault/logo")
    @need("vault_edit")
    def logo_upload():
        f = request.files.get("file")
        if not f or not f.filename:
            raise AppError("Please choose a logo image (PNG, JPG or WebP).")
        try:
            value = logo.make_asset(f.read(), f.filename)
        except ValueError as exc:
            raise AppError(str(exc))
        except Exception:
            raise AppError("That file could not be read as an image.", 422)
        vault.set_asset(db, "logo", value, g.user, kind="image", notes="Approved logo used by the logo check (V-4)")
        return jsonify(ok=True, width=value["width"], height=value["height"])

    @app.get("/api/vault/logo")
    @need()
    def logo_get():
        a = vault.get_asset(db, "logo", None)
        if not a or not a.get("png_b64"):
            raise AppError("No logo has been uploaded yet.", 404)
        return logo.logo_bytes(a), 200, {"Content-Type": "image/png"}

    @app.delete("/api/vault/logo")
    @need("vault_edit")
    def logo_delete():
        db.run("DELETE FROM assets WHERE name='logo'")
        audit.log(db, g.user["name"], "asset.delete", "asset", None, {"name": "logo"})
        return jsonify(ok=True)

    # ------------------------------------------------------------ settings, alerts and scheduler
    def settings_view():
        st = notifier.channel_status(db, cfg)
        out = {"hybrid": {"enabled": settings.hybrid_enabled(db, cfg), "install_default": bool(cfg["HYBRID"]),
                          "embeddings_installed": __import__("claimpassport.engine.semantic", fromlist=["x"]).embeddings_installed(),
                          "ai_judge_available": llm.available},
               "channels": st, "email_from": cfg["SMTP_FROM"] if st["email"] else None,
               "prefs": notifier.get_prefs(db, g.user["id"]), "database": db.kind,
               "can": {"hybrid": security.can(g.user["role"], "settings"), "integrations": security.can(g.user["role"], "integrations")}}
        if security.can(g.user["role"], "settings"):
            out["scheduler"] = scheduler.status()
        return out

    @app.get("/api/settings")
    @need()
    def settings_get():
        return jsonify(settings_view())

    @app.put("/api/settings")
    @need()
    def settings_put():
        b = body()
        changed = []
        if "hybrid" in b:
            if not security.can(g.user["role"], "settings"):
                raise AppError("Only a manager or admin can change verification mode.", 403)
            settings.put(db, "hybrid_mode", "1" if b["hybrid"] else "0", g.user["name"])
            changed.append("hybrid")
        for key in ("slack_webhook_url", "webhook_url", "webhook_secret"):
            if key in b:
                if not security.can(g.user["role"], "integrations"):
                    raise AppError("Only an admin can change Slack and webhook settings.", 403)
                val = (b[key] or "").strip()
                if val and key.endswith("_url"):
                    notifier.check_url(val)
                settings.put_secret(db, cfg, key, val, g.user["name"])
                changed.append(key)
        audit.log(db, g.user["name"], "settings.update", "system", None, {"changed": changed})
        return jsonify(settings_view())

    @app.put("/api/notification-prefs")
    @need()
    def prefs_put():
        prefs = notifier.set_prefs(db, g.user["id"], body())
        audit.log(db, g.user["name"], "prefs.update", "user", g.user["id"], prefs)
        return jsonify(prefs=prefs)

    @app.post("/api/settings/test-alert")
    @need("settings")
    def settings_test_alert():
        return jsonify(results=notifier.send_test(db, cfg, g.user))

    @app.get("/api/scheduler")
    @need("watcher")
    def scheduler_status():
        return jsonify(**scheduler.status(), deliveries=db.q("SELECT * FROM alert_deliveries ORDER BY id DESC LIMIT 30"))

    @app.post("/api/scheduler/run")
    @need("watcher")
    def scheduler_run():
        return jsonify(run=scheduler.run_job("manual"))

    # ------------------------------------------------------------ accuracy lab
    @app.get("/api/accuracy/latest")
    @need("insights")
    def accuracy_latest():
        return jsonify(run=accuracy.latest_run(db), can_run=security.can(g.user["role"], "watcher"),
                       ai_judge_available=llm.available)

    @app.post("/api/accuracy/run")
    @need("watcher")
    def accuracy_run():
        result = accuracy.run_benchmark(cfg, ("rules", "hybrid", "hybrid+ai"), llm=llm)
        accuracy.save_run(db, result, g.user["name"])
        audit.log(db, g.user["name"], "accuracy.run", "system", None, {"sentences": result["dataset"]["size"]})
        return jsonify(run=accuracy.latest_run(db))

    # ------------------------------------------------------------ frontend
    front = BASE_DIR / "frontend"

    @app.get("/")
    def index():
        return send_from_directory(front, "index.html")

    @app.get("/<path:path>")
    def static_files(path):
        if path.startswith("api/"):
            return jsonify(error="Not found."), 404
        if (front / path).is_file():
            return send_from_directory(front, path)
        return send_from_directory(front, "index.html")

    return app
