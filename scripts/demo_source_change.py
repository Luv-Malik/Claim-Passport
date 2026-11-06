"""Demo helper: change an approved fact (the Pro plan price) and show what the watcher does.
Start the app first (python run.py), then:  python scripts/demo_source_change.py [base_url]"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000").rstrip("/")


def call(path, body=None, method=None, token=None):
    req = urllib.request.Request(BASE + path, method=method or ("POST" if body is not None else "GET"),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


token = call("/api/login", {"email": "admin@demo.cp", "password": "demo1234"})["token"]
before = call("/api/insights/overview", token=token)["truth_debt"]
facts = {f["key"]: f for f in call("/api/vault/facts", token=token)["facts"]}
f = facts["price_pro"]
res = call(f"/api/vault/facts/{f['id']}", {"statement": "The Pro plan costs Rs. 1,399 per month.", "value": "Rs. 1,399",
                                           "note": "Demo price change"}, "PUT", token)
after = call("/api/insights/overview", token=token)["truth_debt"]
print(f"Truth Debt before: {before['score']}%  after: {after['score']}%")
print(f"Published pages flagged: {res['proposals_created']}; open the dashboard and the Alerts page to see the suggested fixes.")
