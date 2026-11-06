# Privacy and AI use

## What the platform does by default

- All checking runs **inside your server** with a rules engine. No content is sent to any outside service.
- The AI helper is **off** unless `ANTHROPIC_API_KEY` is set and `CP_USE_LLM=1`.

## If you switch the AI helper on

- It is used only to **suggest extra rewrites** for up to three important findings per review. It cannot approve, reject, publish or change anything.
- What is sent: one sentence, the issue text and the approved statement.
- Before sending: personal data (emails, phone numbers, PAN, Aadhaar-style numbers, card numbers) is masked.
- **Confidential facts are never sent.** For those findings the approved statement is replaced by "none".
- Every call is written to the **AI Transparency log** (visible per content item and in the Audit page): step, engine, model, what was sent, and how many personal items were masked.
- Content can be marked "AI-assisted" by the writer, and this is shown to reviewers.

## Confidential material

- A fact marked **confidential** is hidden from writers (they see "(confidential fact)") and is never listed in the public Truth Feed. Messages and suggestions about it do not reveal its value.
- Reviewers, managers and admins can see confidential facts.
- Uploaded files are stored in `CP_UPLOAD_DIR` on your server and are not served back publicly.

## What is not done yet

- No encryption of data inside the app. Use disk encryption or an encrypted database in production.
- No data-retention or deletion tools yet.
- The demo passwords and default secret key must be replaced before real use.
- The Truth Feed is public by design. Review which facts are marked confidential before exposing the service.
