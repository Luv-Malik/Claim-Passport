"""The Brand Vault: approved facts, rules (from guidelines), glossary and assets."""
import re

from . import audit, clock
from .db import jdump, jload
from .errors import AppError

CATEGORIES = ("tone", "terminology", "messaging", "accessibility", "visual", "claims")

BUILTIN_RULES = [
    dict(code="TERM-1", category="terminology", title="Use the approved product names and terms", severity="medium",
         kind="glossary", guideline_ref="Brand Guidelines v3, section 2 (Terminology)",
         description="Names and terms in the glossary must be written the approved way."),
    dict(code="T-1", category="tone", title="Keep a professional, friendly voice (no slang)", severity="low", kind="terms",
         guideline_ref="Brand Guidelines v3, section 1.1 (Voice)",
         config={"pairs": {"awesome": ["great", "excellent"], "gonna": ["going to"], "wanna": ["want to"],
                           "super cool": ["impressive"], "kinda": ["somewhat"], "stuff": ["things", "items"]}}),
    dict(code="T-2", category="tone", title="Use at most one exclamation mark", severity="low", kind="builtin",
         guideline_ref="Brand Guidelines v3, section 1.2", config={"check": "exclaim", "max": 1}),
    dict(code="T-3", category="tone", title="Do not write words in ALL CAPS", severity="low", kind="builtin",
         guideline_ref="Brand Guidelines v3, section 1.3",
         config={"check": "caps", "min_len": 4, "allow": ["ISO", "GDPR", "HIPAA", "SOC", "API", "SMS", "GST", "UPI",
                                                          "FAQ", "PDF", "CSV", "SLA", "IST", "HTML", "CSS", "JSON"]}),
    dict(code="A-1", category="accessibility", title="Keep sentences short (under 28 words)", severity="low",
         kind="builtin", guideline_ref="Brand Guidelines v3, section 5.1 (Readability)",
         config={"check": "readability", "max_words": 28}),
    dict(code="A-2", category="accessibility", title="Every image needs alt text", severity="medium", kind="builtin",
         guideline_ref="Brand Guidelines v3, section 5.2 (Images)", config={"check": "alt_text"}),
    dict(code="A-3", category="accessibility", title="Links must describe where they go", severity="low",
         kind="builtin", guideline_ref="Brand Guidelines v3, section 5.3 (Links)",
         config={"check": "link_text", "generic": ["click here", "here", "read more", "learn more", "more", "link"]}),
    dict(code="A-4", category="accessibility", title="Text must have enough colour contrast (WCAG 4.5:1)",
         severity="high", kind="builtin", guideline_ref="Brand Guidelines v3, section 5.4 (Contrast)",
         config={"check": "contrast", "min_ratio": 4.5}),
    dict(code="A-5", category="accessibility", title="Use inclusive language", severity="low", kind="terms",
         guideline_ref="Brand Guidelines v3, section 5.5 (Inclusive language)",
         config={"pairs": {"guys": ["everyone", "team"], "crazy": ["surprising"], "blind to": ["unaware of"],
                           "sanity check": ["quick check"], "whitelist": ["allowlist"], "blacklist": ["blocklist"],
                           "manpower": ["workforce"]}}),
    dict(code="M-1", category="messaging", title="Prices and offers must say 'Terms apply'", severity="medium",
         kind="requires", guideline_ref="Brand Guidelines v3, section 3.1 (Offers)",
         config={"trigger": r"(?:Rs\.?|₹|INR)\s?\d[\d,]*|\bper (?:month|year)\b|\d+\s?%\s?off",
                 "required": r"terms (?:and conditions )?apply|T&C|see terms", "append": "Terms apply.",
                 "message": "This text mentions a price or an offer but does not say 'Terms apply'."}),
    dict(code="M-2", category="messaging", title="Never promise legal or tax outcomes", severity="high", kind="regex",
         guideline_ref="Brand Guidelines v3, section 3.2 (Legal promises)", human_lock=1,
         config={"pattern": r"\b(?:avoid|eliminate|never pay)\s+(?:all\s+)?(?:tax(?:es)?|penalt(?:y|ies)|audits?)\b|"
                            r"\b(?:tax|legally)[- ]compliant\b", "flags": "i",
                 "message": "This sounds like a legal or tax promise. Only Legal can approve wording like this.",
                 "advice": "Describe what the product does (for example, 'helps you prepare GST-ready invoices')."}),
    dict(code="V-1", category="visual", title="Use only brand colours", severity="medium", kind="builtin",
         guideline_ref="Brand Guidelines v3, section 4.1 (Colour)", config={"check": "palette", "tolerance": 40}),
    dict(code="V-2", category="visual", title="Use only brand fonts", severity="medium", kind="builtin",
         guideline_ref="Brand Guidelines v3, section 4.2 (Fonts)", config={"check": "fonts"}),
    dict(code="V-3", category="visual", title="Images must follow size, shape and colour rules", severity="medium",
         kind="builtin", guideline_ref="Brand Guidelines v3, section 4.3 (Images)",
         config={"check": "image", "coverage": 0.2, "distance": 70, "ratio_tolerance": 0.05}),
    dict(code="C-1", category="claims", title="Bold claims need an approved source", severity="high", kind="claim",
         guideline_ref="Brand Guidelines v3, section 6.1 (Claims)"),
    dict(code="C-2", category="claims", title="Numbers must match the approved fact", severity="high", kind="claim",
         guideline_ref="Brand Guidelines v3, section 6.2 (Numbers)"),
    dict(code="C-3", category="claims", title="Do not use facts whose source has expired", severity="medium",
         kind="claim", guideline_ref="Brand Guidelines v3, section 6.3 (Freshness)"),
    dict(code="C-4", category="claims", title="Numbers need an approved source", severity="medium", kind="claim",
         guideline_ref="Brand Guidelines v3, section 6.2 (Numbers)"),
    dict(code="C-5", category="claims", title="Comparisons with other brands need Legal review", severity="high",
         kind="claim", human_lock=1, guideline_ref="Brand Guidelines v3, section 6.4 (Comparisons)"),
    dict(code="C-6", category="claims", title="Wording must not go beyond or against an approved fact (meaning check)",
         severity="high", kind="claim", guideline_ref="Brand Guidelines v3, section 6.2 (Numbers) and 6.1 (Claims)",
         description="Found by hybrid verification: claims written in other words, such as 'our help desk never sleeps' "
                     "or 'millions of users', checked against the approved facts."),
    dict(code="V-4", category="visual", title="The approved logo must be present, large enough and not at the edge",
         severity="medium", kind="builtin", guideline_ref="Brand Guidelines v3, section 4.4 (Logo)",
         config={"check": "logo"}, description="Image uploads are searched for the approved logo (Vault > Assets)."),
]

DEFAULT_ASSETS = {
    "palette": {"kind": "config", "value": [
        {"hex": "#17202A", "role": "text", "name": "Navy"}, {"hex": "#C75B0B", "role": "primary", "name": "Orange"},
        {"hex": "#127C7A", "role": "accent", "name": "Teal"}, {"hex": "#2F6DB5", "role": "accent", "name": "Blue"},
        {"hex": "#F4F2EC", "role": "background", "name": "Cream"}, {"hex": "#FFFFFF", "role": "background", "name": "White"}]},
    "fonts": {"kind": "config", "value": ["Inter", "Georgia"]},
    "image_rules": {"kind": "config", "value": {"ratios": [1.0, 1.7778, 1.91, 0.8], "min_width": 1000}},
}


# ------------------------------------------------------------------ facts
FACT_FIELDS = ("key", "statement", "value", "category", "source_doc", "source_ref", "owner", "confidential",
               "verified_on", "expires_on", "review_interval_days", "keywords")


def list_facts(db, include_inactive=False):
    sql = "SELECT * FROM facts" + ("" if include_inactive else " WHERE active=1") + " ORDER BY category, key"
    return db.q(sql)


def get_fact(db, fact_id):
    f = db.one("SELECT * FROM facts WHERE id=?", (fact_id,))
    if not f:
        raise AppError("Fact not found.", 404)
    return f


def create_fact(db, data, actor):
    key = (data.get("key") or "").strip()
    statement = (data.get("statement") or "").strip()
    if not key or not statement:
        raise AppError("A fact needs a key and a statement.")
    if db.one("SELECT id FROM facts WHERE key=?", (key,)):
        raise AppError(f"A fact with key '{key}' already exists.", 409)
    today = clock.today()
    d = {k: data.get(k) for k in FACT_FIELDS if data.get(k) is not None}
    d.setdefault("category", "general")
    d.setdefault("verified_on", today.isoformat())
    interval = int(d.get("review_interval_days") or 90)
    d["review_interval_days"] = interval
    if not d.get("expires_on"):
        d["expires_on"] = (clock.parse_date(d["verified_on"]) + __import__("datetime").timedelta(days=interval)).isoformat()
    d.update(version=1, active=1, updated_at=clock.now(), confidential=1 if d.get("confidential") else 0)
    fid = db.insert("facts", d)
    db.insert("fact_versions", {"fact_id": fid, "version": 1, "statement": statement, "value": d.get("value", ""),
                                "verified_on": d["verified_on"], "expires_on": d["expires_on"],
                                "changed_by": actor["name"] if actor else "system", "changed_at": clock.now(),
                                "note": "Created"})
    audit.log(db, actor["name"] if actor else "system", "fact.create", "fact", fid, {"key": key})
    return get_fact(db, fid)


def update_fact(db, fact_id, data, actor, note=""):
    """Update a fact. Returns (before, after). `version` goes up only when the statement or value changes,
    because that is what makes published content wrong."""
    before = get_fact(db, fact_id)
    changes = {k: data[k] for k in FACT_FIELDS if k in data and data[k] != before.get(k) and k != "key"}
    if "confidential" in changes:
        changes["confidential"] = 1 if changes["confidential"] else 0
    if not changes:
        return before, before
    content_changed = any(k in changes for k in ("statement", "value"))
    if content_changed:
        changes["version"] = before["version"] + 1
    # Re-verifying without a new expiry date extends it by the review interval.
    if "verified_on" in changes and "expires_on" not in changes:
        interval = int(changes.get("review_interval_days") or before["review_interval_days"] or 90)
        changes["expires_on"] = (clock.parse_date(changes["verified_on"]) + __import__("datetime").timedelta(days=interval)).isoformat()
    changes["updated_at"] = clock.now()
    db.update("facts", fact_id, changes)
    after = get_fact(db, fact_id)
    db.insert("fact_versions", {"fact_id": fact_id, "version": after["version"], "statement": after["statement"],
                                "value": after["value"], "verified_on": after["verified_on"],
                                "expires_on": after["expires_on"], "changed_by": actor["name"],
                                "changed_at": clock.now(), "note": note or ("Changed: " + ", ".join(sorted(changes)))})
    audit.log(db, actor["name"], "fact.update", "fact", fact_id, {"fields": sorted(changes), "version": after["version"]})
    return before, after


def fact_history(db, fact_id):
    get_fact(db, fact_id)
    return db.q("SELECT * FROM fact_versions WHERE fact_id=? ORDER BY id DESC", (fact_id,))


# ------------------------------------------------------------------ rules
def _rule_out(r):
    r = dict(r)
    r["config"] = jload(r.get("config"), {})
    return r


def list_rules(db):
    return [_rule_out(r) for r in db.q("SELECT * FROM rules ORDER BY category, code")]


def rules_by_code(db):
    return {r["code"]: r for r in list_rules(db)}


def ensure_builtin_rules(db):
    for r in BUILTIN_RULES:
        if not db.one("SELECT id FROM rules WHERE code=?", (r["code"],)):
            db.insert("rules", {"code": r["code"], "category": r["category"], "title": r["title"],
                                "description": r.get("description", ""), "severity": r.get("severity", "medium"),
                                "kind": r["kind"], "config": jdump(r.get("config", {})),
                                "guideline_ref": r.get("guideline_ref", ""), "human_lock": r.get("human_lock", 0)})
    for name, a in DEFAULT_ASSETS.items():
        if not db.one("SELECT id FROM assets WHERE name=?", (name,)):
            db.insert("assets", {"name": name, "kind": a["kind"], "value": jdump(a["value"]), "notes": ""})


def update_rule(db, code, data, actor):
    r = db.one("SELECT * FROM rules WHERE code=?", (code,))
    if not r:
        raise AppError("Rule not found.", 404)
    allowed = {k: data[k] for k in ("title", "description", "severity", "guideline_ref", "human_lock", "active")
               if k in data}
    if "config" in data and isinstance(data["config"], dict):
        allowed["config"] = jdump(data["config"])
    if "severity" in allowed and allowed["severity"] not in ("low", "medium", "high"):
        raise AppError("Severity must be low, medium or high.")
    for k in ("human_lock", "active"):
        if k in allowed:
            allowed[k] = 1 if allowed[k] else 0
    db.update("rules", r["id"], allowed)
    audit.log(db, actor["name"], "rule.update", "rule", r["id"], {"code": code, "fields": sorted(allowed)})
    return _rule_out(db.one("SELECT * FROM rules WHERE id=?", (r["id"],)))


_RULE_LINE = re.compile(r"^[-*]\s*\[([A-Za-z]+-?\d+[A-Za-z]*)\]\s*(.*)$")
_KEYS = re.compile(r"\b(avoid|use|severity|lock|ref):", re.I)


def parse_guidelines(markdown):
    """Turn a guidelines markdown file into structured rules. See docs/GUIDELINE_FORMAT.md."""
    rules, category = [], "tone"
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("#"):
            head = line.lstrip("#").strip().lower()
            for c in CATEGORIES:
                if head.startswith(c):
                    category = c
            continue
        m = _RULE_LINE.match(line)
        if not m:
            continue
        code, rest = m.group(1).upper(), m.group(2)
        parts = _KEYS.split(rest)
        title = parts[0].strip().rstrip(".")
        opts = {}
        for i in range(1, len(parts) - 1, 2):
            opts[parts[i].lower()] = parts[i + 1].strip()
        avoid = re.findall(r'"([^"]+)"', opts.get("avoid", ""))
        use = re.findall(r'"([^"]+)"', opts.get("use", ""))
        rule = {"code": code, "category": category, "title": title, "kind": "note",
                "severity": (opts.get("severity") or "").strip().lower() or None,
                "guideline_ref": opts.get("ref", "").strip(),
                "human_lock": (1 if opts["lock"].strip().lower() in ("yes", "true", "1") else 0) if "lock" in opts else None,
                "config": {}}
        if rule["severity"] not in ("low", "medium", "high"):
            rule["severity"] = None
        if avoid:
            rule["kind"] = "terms"
            if use and len(use) == len(avoid):
                rule["config"] = {"pairs": {a: [u] for a, u in zip(avoid, use)}}
            else:
                rule["config"] = {"pairs": {a: use for a in avoid}}
        rules.append(rule)
    return rules


def import_guidelines(db, markdown, title, version, actor):
    parsed = parse_guidelines(markdown)
    if not parsed:
        raise AppError("No rules found. Rule lines look like: - [T-9] Title. avoid: \"x\" use: \"y\"")
    db.insert("guideline_docs", {"title": title or "Guidelines", "version": version or "1", "content": markdown,
                                 "created_at": clock.now()})
    created, updated = 0, 0
    for r in parsed:
        ex = db.one("SELECT * FROM rules WHERE code=?", (r["code"],))
        if ex:
            upd = {"title": r["title"]}
            if r["severity"]:
                upd["severity"] = r["severity"]
            if r["human_lock"] is not None:
                upd["human_lock"] = r["human_lock"]
            if r["guideline_ref"]:
                upd["guideline_ref"] = r["guideline_ref"]
            if ex["kind"] in ("note", "terms") and r["kind"] != "note":
                upd.update(kind=r["kind"], config=jdump(r["config"]))
            db.update("rules", ex["id"], upd)
            updated += 1
        else:
            db.insert("rules", {"code": r["code"], "category": r["category"], "title": r["title"],
                                "severity": r["severity"] or "medium", "kind": r["kind"], "config": jdump(r["config"]),
                                "guideline_ref": r["guideline_ref"] or f"{title or 'Guidelines'} {version or ''}".strip(),
                                "human_lock": r["human_lock"] or 0})
            created += 1
    audit.log(db, actor["name"], "guidelines.import", "guideline_doc", None, {"created": created, "updated": updated})
    return {"created": created, "updated": updated, "total": len(parsed)}


# ------------------------------------------------------------------ glossary and assets
def list_glossary(db):
    out = db.q("SELECT * FROM glossary ORDER BY preferred")
    for g in out:
        g["banned"] = jload(g["banned"], [])
    return out


def add_glossary(db, data, actor):
    preferred = (data.get("preferred") or "").strip()
    banned = [b.strip() for b in (data.get("banned") or []) if b.strip()]
    if not preferred or not banned:
        raise AppError("A glossary entry needs a preferred term and at least one term to avoid.")
    gid = db.insert("glossary", {"preferred": preferred, "banned": jdump(banned), "kind": data.get("kind", "term"),
                                 "note": data.get("note", ""), "case_sensitive": 1 if data.get("case_sensitive") else 0})
    audit.log(db, actor["name"], "glossary.add", "glossary", gid, {"preferred": preferred})
    return gid


def delete_glossary(db, gid, actor):
    db.run("DELETE FROM glossary WHERE id=?", (gid,))
    audit.log(db, actor["name"], "glossary.delete", "glossary", gid)


def get_asset(db, name, default=None):
    a = db.one("SELECT * FROM assets WHERE name=?", (name,))
    return jload(a["value"], default) if a else default


def list_assets(db):
    out = db.q("SELECT * FROM assets ORDER BY name")
    for a in out:
        a["value"] = jload(a["value"], {})
    return out


def set_asset(db, name, value, actor, kind="config", notes=""):
    a = db.one("SELECT * FROM assets WHERE name=?", (name,))
    if a:
        db.update("assets", a["id"], {"value": jdump(value), "notes": notes or a["notes"]})
    else:
        db.insert("assets", {"name": name, "kind": kind, "value": jdump(value), "notes": notes})
    audit.log(db, actor["name"], "asset.set", "asset", None, {"name": name})
