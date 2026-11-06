"""Demo data: a fictional brand ("Lumio Invoice"), demo users, facts, guidelines, sample content and some
history, so every screen has something real to show. Safe to run once on an empty database."""
import datetime as dt
import json

from . import audit, clock, security, vault, watcher, workflow
from .config import BASE_DIR

SAMPLE = BASE_DIR / "data" / "sample"
DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("Admin User", "admin@demo.cp", "admin", "Platform"),
    ("Anil Kapoor", "anil@demo.cp", "manager", "Marketing"),
    ("Meera Iyer", "meera@demo.cp", "reviewer", "Legal"),
    ("Priya Sharma", "priya@demo.cp", "creator", "Agency North"),
    ("Rohan Mehta", "rohan@demo.cp", "creator", "Social Media"),
    ("Kabir Rao", "kabir@demo.cp", "creator", "Agency North"),
]


def add_user(db, name, email, role, team="", password=DEMO_PASSWORD):
    return db.insert("users", {"name": name, "email": email.lower(), "password_hash": security.hash_password(password),
                               "role": role, "team": team, "created_at": clock.now()})


def bootstrap_admin(db, email=None, password=None):
    """Used when demo data is switched off: create the first admin account."""
    import os
    email = email or os.environ.get("CP_ADMIN_EMAIL", "admin@example.com")
    password = password or os.environ.get("CP_ADMIN_PASSWORD", "change-me-now")
    add_user(db, "Administrator", email, "admin", "Platform", password)
    return email


def _user(db, email):
    return db.one("SELECT * FROM users WHERE email=?", (email,))


def _flow(db, cfg, owner, reviewer, manager, title, fmt, text, channel, publish=True):
    cid = workflow.create_content(db, cfg, owner, title, fmt, text, {}, channel)
    if publish:
        workflow.submit(db, owner, cid)
        workflow.approve(db, reviewer, cid, "Looks good.")
        workflow.publish(db, cfg, manager, cid)
    return cid


def seed_demo(db, cfg=None, llm=None):
    cfg = cfg or {}
    if db.one("SELECT id FROM users LIMIT 1"):
        return False
    vault.ensure_builtin_rules(db)
    for n, e, r, t in DEMO_USERS:
        add_user(db, n, e, r, t)
    admin, manager, reviewer = _user(db, "admin@demo.cp"), _user(db, "anil@demo.cp"), _user(db, "meera@demo.cp")
    priya, rohan, kabir = _user(db, "priya@demo.cp"), _user(db, "rohan@demo.cp"), _user(db, "kabir@demo.cp")
    today = clock.today()

    # Guidelines -> structured rules; glossary; facts
    vault.import_guidelines(db, (SAMPLE / "brand_guidelines.md").read_text("utf-8"), "Lumio Invoice Brand Guidelines", "v3", admin)
    for g in json.loads((SAMPLE / "glossary.json").read_text("utf-8")):
        vault.add_glossary(db, g, admin)
    for f in json.loads((SAMPLE / "approved_facts.json").read_text("utf-8")):
        d = {k: v for k, v in f.items() if k not in ("days_since_verified", "expires_in_days")}
        d["verified_on"] = (today - dt.timedelta(days=f["days_since_verified"])).isoformat()
        d["expires_on"] = (today + dt.timedelta(days=f["expires_in_days"])).isoformat()
        if f["key"] == "price_starter":   # the price will change later in this seed, so published pages go stale
            d.update(statement="The Starter plan costs Rs. 449 per month.", value="Rs. 449")
        vault.create_fact(db, d, admin)

    # An older page published when the Starter plan cost Rs. 449
    _flow(db, cfg, rohan, reviewer, manager, "Pricing page", "text",
          "Lumio Invoice has a 99.9% uptime commitment in its service agreement. The Starter plan costs Rs. 449 per month. Terms apply.", "website")
    # ... then the price changes. The watcher prepares a fix for the owner.
    before, after = vault.update_fact(db, db.one("SELECT id FROM facts WHERE key='price_starter'")["id"],
                                      {"statement": "The Starter plan costs Rs. 499 per month.", "value": "Rs. 499"}, admin, "New price list v7")
    watcher.on_fact_changed(db, before, after, admin)
    # A clean newsletter, published with the current facts
    _flow(db, cfg, kabir, reviewer, manager, "November newsletter", "text", (SAMPLE / "content" / "newsletter.txt").read_text("utf-8"), "email")

    # Drafts with real mistakes, to review in the demo
    drafts = [("Launch blog: new Lumio Invoice", "markdown", "launch_blog.md", "website", priya),
              ("Social post: product launch", "text", "social_post.txt", "social", rohan),
              ("Landing page", "html", "landing_page.html", "website", priya),
              ("Ad copy: annual plans", "text", "ad_copy.txt", "ads", kabir)]
    for title, fmt, fn, ch, owner in drafts:
        workflow.create_content(db, cfg, owner, title, fmt, (SAMPLE / "content" / fn).read_text("utf-8"), {}, ch, llm=llm)
    banner = SAMPLE / "content" / "banner.png"
    if banner.exists():
        from . import ingest
        r = ingest.extract("banner.png", banner.read_bytes())
        workflow.create_content(db, cfg, rohan, "Instagram banner", r["fmt"], r["text"], r["meta"], "social", filename="banner.png")

    _history(db, cfg, priya, rohan, kabir, today)
    audit.log(db, "system", "seed.demo", "system", None, {"users": len(DEMO_USERS)})
    return True


def _history(db, cfg, priya, rohan, kabir, today):
    """Past reviews so the Insights pages show real patterns (repeated mistakes, an unclear rule)."""
    past = [
        (rohan, "Social post: Monday tips", "Awesome tips are live!! Check them out! Our users love them!!", 12),
        (rohan, "Social post: Tuesday poll", "Vote now! What should we build next?! Tell us!!", 11),
        (priya, "Blog: invoicing basics", "Sending a clear invoice helps you get paid. BE CLEAR about dates! Add your logo!", 9),
        (kabir, "Email: reminders", "Never forget a payment again! It is SUPER easy! Try it today!!", 7),
        (rohan, "Social post: weekend", "Weekend vibes!! Our TEAM is gonna keep shipping stuff!!", 5),
        (priya, "Blog: tax season", "Tax season is easy. Do not miss any DEADLINE this year! Stay ready!", 3),
    ]
    reasons_unclear = ["Not sure what counts as too many exclamation marks in a launch post.",
                       "The rule on exclamation marks is unclear for social posts."]
    t2_seen = 0
    for owner, title, text, days_ago in past:
        cid = workflow.create_content(db, cfg, owner, title, "text", text, {}, "social" if owner["team"] == "Social Media" else "website")
        stamp = (today - dt.timedelta(days=days_ago)).isoformat() + "T10:00:00Z"
        db.run("UPDATE findings SET created_at=? WHERE content_id=?", (stamp, cid))
        db.run("UPDATE contents SET created_at=?, updated_at=? WHERE id=?", (stamp, stamp, cid))
        for f in workflow.findings_for(db, cid, 1):
            if f["rule_code"] == "T-2":
                t2_seen += 1
                if t2_seen % 5 in (1, 2, 3):       # most T-2 findings get rejected: the rule is probably unclear
                    workflow.decide(db, owner, f["id"], "rejected", reasons_unclear[t2_seen % 2] if t2_seen % 5 != 3 else "Our launch posts always use more than one.")
                else:
                    workflow.decide(db, owner, f["id"], "accepted", "", 0)
            elif f["rule_code"] in ("T-1", "A-5", "T-3"):
                workflow.decide(db, owner, f["id"], "accepted", "", 0)
