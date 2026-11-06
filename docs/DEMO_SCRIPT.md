# Demo script (about 6 minutes)

Start fresh: `make reset && python run.py`. All accounts use password `demo1234`.

**Setup line:** "Lumio Invoice is a made-up company. Its content comes from agencies, social teams and AI tools. Claim Passport checks all of it before publishing, and keeps checking after."

## 1. A writer gets help, not a rejection (Priya, creator)
1. Open **Content > Landing page** (or **Launch blog**).
2. Show a finding: highlighted text, plain reason, the exact guideline or fact (with page), confidence.
3. Click **Use this fix** on a wrong price. Point out: only the number changes, the sentence stays.
4. Click **Keep as written** on a high-risk claim. It is refused: only a reviewer can keep it. That is human control.
5. Click **Apply changes**, then **Versions > Compare** to show the tracked change.

## 2. Review and approval (Meera, reviewer; Anil, manager)
1. As Rohan, submit a clean piece (paste: `The Starter plan costs Rs. 499 per month. Terms apply.`).
2. As Meera, open it and **Approve**.
   Then, as Priya, submit the launch blog without fixing anything. As Meera, try to approve it: it is blocked while findings that need a person are open.
3. As Anil, **Publish**. Open the **Passports** tab: each claim is linked to its source.

## 3. The wow moment: a source changes (Anil)
1. Dashboard: **Pricing page** already shows *Source changed* and a suggested fix waits under **Alerts** (the Starter price moved from Rs. 449 to Rs. 499 after it was published).
2. **Brand Vault > Approved facts**: edit `price_pro`, change the value to `Rs. 1,399`, save. Toast: published pages now need a fix. (Or run `python scripts/demo_source_change.py`.)
3. Dashboard: Truth Debt goes up. **Alerts**: old text vs new text. **Apply as new draft** (it goes back through review).

## 4. Insights (Anil)
1. **Insights**: repeated mistakes by rule and team.
2. **Guidelines that may be unclear**: T-2 (exclamation marks) is rejected most of the time, with the reasons people gave, and a suggestion to add examples.
3. **Claim half-life**: which fact goes stale next.

## 5. Trust and proof
1. **Proof Time Machine**: pick the Pricing page and a date. Show what was live and whether the source was consistent that day.
2. Open **Truth Feed**: verified facts for AI assistants, with a button for the raw JSON (`/.well-known/claims.json`). Confidential and expired facts are missing on purpose.
3. **Audit and AI log** (admin): who did what, and where AI or outside services were used (here: nowhere, the rules engine runs locally).

## Different file types (optional)
Upload `data/sample/content/banner.png` (off-brand colours, small size, a bold claim read from the picture with OCR), `product_brief.pdf` (wrong customer count) or `landing_page.html` (low contrast, wrong font, image without alt text).
