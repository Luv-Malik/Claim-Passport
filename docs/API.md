# API reference

All endpoints return JSON. Send `Authorization: Bearer <token>` (from `POST /api/login`) except where marked public. Errors look like `{"error": "message"}` with a suitable status code (400, 401, 403, 404, 409, 413, 415, 429).

## Public
| Method and path | Purpose |
|---|---|
| `GET /api/health` | health check |
| `GET /api/meta` | version, roles, whether AI helper is on, disclosure text |
| `GET /.well-known/claims.json` (also `/api/public/claims`) | Truth Feed: verified, non-confidential, non-expired facts |
| `POST /api/login` | `{email, password}` returns `{token, user}` |

## Content and review
| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/contents?status=&q=` | any (creators see own) | list content |
| `POST /api/contents` | any | JSON `{title, text, fmt, channel, ai_assisted}` or multipart with `file`, `title`, `channel`, `alt_text`, `ai_assisted` |
| `GET /api/contents/<id>` | owner or non-creator | content, findings, comments, versions, approvals, allowed actions, passports, proposals |
| `GET /api/contents/<id>/text?version=` | same | plain text of a version |
| `POST /api/contents/<id>/versions` | owner, manager, admin | new version `{text, note}` (re-analysed) |
| `POST /api/contents/<id>/alt-text` | same | `{alt_text}` for image uploads |
| `POST /api/contents/<id>/analyze` | same | re-run the checks |
| `POST /api/findings/<id>/decision` | any | `{decision: accepted/edited/rejected/open, reason, suggestion_index, final_text}` |
| `POST /api/contents/<id>/apply` | same | build the next version from accepted/edited changes |
| `GET /api/contents/<id>/diff?from=&to=` | same | word-level differences |
| `POST /api/contents/<id>/submit` | owner, manager, admin | send for review |
| `POST /api/contents/<id>/approve` | reviewer, manager, admin (not the owner) | approve `{note}` |
| `POST /api/contents/<id>/request-changes` | same | `{note}` |
| `POST /api/contents/<id>/publish` | manager, admin | publish and create claim passports |
| `GET/POST /api/contents/<id>/comments` | any with access | comments `{body, anchor_start, anchor_end}` |
| `GET /api/contents/<id>/transparency` | any with access | AI and service use for this content |

## Vault
| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/vault/summary`, `/facts`, `/rules`, `/glossary`, `/assets` | any | read (confidential facts masked for creators) |
| `POST /api/vault/facts`, `PUT /api/vault/facts/<id>` | manager, admin | create or update a fact (a changed statement or value triggers the watcher) |
| `GET /api/vault/facts/<id>/history` | reviewer+ | version history |
| `PUT /api/vault/rules/<code>` | manager, admin | `{severity, human_lock, active, title, config}` |
| `POST /api/vault/guidelines/import` | manager, admin | `{markdown, title, version}` |
| `POST /api/vault/glossary`, `DELETE /api/vault/glossary/<id>` | manager, admin | glossary |
| `PUT /api/vault/assets/<name>` | manager, admin | `{value}` (palette, fonts, image_rules) |

## Passports, watcher, proof
| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/passports?status=` | any (creators see own) | live passports |
| `POST /api/watcher/run` | manager, admin | scan for expiring and expired sources |
| `GET /api/proposals`, `POST /api/proposals/<id>/apply`, `/dismiss` | owner, manager, admin | suggested fixes after a source change |
| `GET /api/notifications`, `POST /api/notifications/read` | any | alerts |
| `GET /api/proof?content_id=&at=YYYY-MM-DD` | any with access | Proof Time Machine |
| `GET /api/contents/<id>/timeline` | any with access | publications and source changes for one item (draws the timeline) |

## Insights and admin
| Method and path | Role | Purpose |
|---|---|---|
| `GET /api/insights/overview` | any | dashboard numbers |
| `GET /api/insights/mistakes`, `/guideline-gaps`, `/half-life`, `/trend` | reviewer, manager, admin | governance insights |
| `GET /api/audit` | manager, admin | audit trail and AI log |
| `GET /api/users` | manager, admin | people |
| `POST /api/users` | admin | create a user |

## Round 3 endpoints
| Method and path | Who | Purpose |
|---|---|---|
| GET/PUT `/api/settings` | all read; manager changes `hybrid`; admin changes `slack_webhook_url`, `webhook_url`, `webhook_secret` | Verification mode and channels (addresses are never returned) |
| PUT `/api/notification-prefs` | self | `email_enabled`, `slack_enabled`, `webhook_enabled`, `digest_enabled` |
| POST `/api/settings/test-alert` | manager | Test every configured channel |
| GET `/api/scheduler`, POST `/api/scheduler/run` | manager | Background scan status, run now |
| GET `/api/accuracy/latest`, POST `/api/accuracy/run` | reviewer+ read; manager run | Accuracy Lab |
| GET `/api/contents/<id>/original` | visible content | Decrypted original upload |
| GET `/api/contents/<id>/pages`, `/pages/<n>` | visible content | PDF page image (data URL) with outlined problems |
| GET `/api/contents/<id>/export`, `/export/report` | visible content | Corrected .docx / .pptx and what could not be applied |
| POST/GET/DELETE `/api/vault/logo` | manager upload; all read | Approved logo for the V-4 check |
