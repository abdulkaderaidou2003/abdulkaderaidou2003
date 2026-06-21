# Aidou Command Enterprise Ultimate — PRD

## Vision
A single mobile command center that unifies HR, payroll, finance, ops, compliance, AI and customer-facing tools for businesses of every size — from small businesses to enterprises, governments, and non-profits across industries (hospitality, retail, construction, healthcare, education, ISP/telecom, property management, manufacturing, transportation, professional services).

One platform · One login · One database · One AI ecosystem · Modular pricing.

## MVP Scope (this build)

### Platform
- Expo React Native (Expo SDK 54) mobile + web preview
- FastAPI + MongoDB backend
- Dark-First command-center design system (rust/ember accent on obsidian/graphite)

### Authentication
- Emergent-managed Google Auth (mobile WebBrowser + web redirect)
- 7-day Bearer token session, stored in expo-secure-store / localStorage

### Multi-company
- Top-bar Company Switcher
- 3 seeded demo companies (Aidou Corporate · Northstar ISP · Summit Construction)
- Switching changes context for all data fetches

### Bottom-tab navigation
1. **Dashboard** — KPI grid (revenue MTD, payroll, pipeline, employees, tickets, customers, alerts), AI executive summary, live operations feed
2. **Modules** — App-launcher hub of 60+ enterprise modules in 8 categories (People · Finance · Sales/Customers · Operations · Compliance/Safety · Communications · Intelligence · IT/Future) with search; live modules badged
3. **AI Command Center** — Horizontal assistant selector (Business Advisor · HR · Accountant · Scheduler · Customer Support · Marketing · Analytics) chatting via streaming GPT-5.2
4. **Alerts** — Compliance and operational alerts feed, severity filter chips, mark-as-read
5. **Profile** — User card, company switcher, account/platform/control rows, sign-out

### Module detail screens (live)
- HR — Employee list with department filter chips and status badges
- Job Tickets — Open / In Progress / Closed segmented control, priority badges, SLA countdown
- Workforce Schedule — Day-grouped shifts with start/end times and department
- CRM — Pipeline value header + customer cards
- 40+ other modules show a "Preview" detail with module pills (require subscription)

## AI Command Center
- Backend `/api/ai/chat` streams via SSE using `emergentintegrations` LlmChat with `openai/gpt-5.2`
- Per-assistant system prompts; history persisted in `ai_messages` collection
- Frontend renders streaming tokens incrementally; supports suggested prompts

## Data model (MongoDB)
- `users`, `user_sessions`, `companies`, `employees`, `tickets`, `shifts`, `customers`, `alerts`, `ai_messages`
- All endpoints return JSON with `_id` excluded; ObjectIds never leak
- Indexes: unique on user_id, email, session_token, company_id+employee_id; TTL on session expires_at

## API surface
- `POST /api/auth/session`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET /api/companies`, `POST /api/companies/switch`
- `GET /api/modules`
- `GET /api/dashboard`
- `GET/POST /api/hr/employees`
- `GET/POST /api/tickets`
- `GET /api/schedule`
- `GET /api/crm/customers`
- `GET /api/alerts`, `POST /api/alerts/{id}/read`
- `POST /api/ai/chat` (SSE), `GET /api/ai/history`

## Future expansion (out of MVP)
- Payroll T4 generation, full POS, fleet GPS live map, drone flight logs, GIS smart maps
- Push notifications via Emergent
- Native builds for store distribution
- IoT, AR support, digital wallet


## Iteration 9 — Per-module router split + Public Trust Score Network (June 2026)

### Backend refactor
- `server.py` split from **1942 lines → 99 lines**. All 180+ endpoints now live in 23 dedicated routers under `/app/backend/routers/*.py`:
  - `auth.py`, `companies.py`, `workspaces.py`, `admin_users.py`, `modules.py`, `dashboard.py`,
    `hr.py`, `tickets.py`, `schedule.py`, `crm.py`, `pos.py`, `payroll.py`, `fleet.py`, `inventory.py`,
    `alerts.py`, `ai.py`, `audit_log.py`, `timeclock.py`, `customer.py`, `marketplace.py`,
    `cash_advance.py`, `underwriting.py`, `root.py`
- Shared infra moved to `/app/backend/core/`:
  - `models.py` (all Pydantic models + `DEFAULT_POLICY`/`DEFAULT_WEIGHTS`)
  - `seed.py` (idempotent indexes + sample data)
  - `email.py` (SendGrid magic-link helper)
  - `scoring.py` (`compute_credit_score`, `snapshot_all_companies`, `build_trust_badge`, signature sign/verify)
  - `catalog.py` (static modules catalog)
- 188 legacy tests + 10 new `test_iteration_9.py` tests = **198/198** passing locally; **234/234** via testing agent.

### Tunable scoring weights
- `GET /api/underwriting/weights` returns defaults from `ScoringWeights` model.
- `PUT /api/underwriting/weights` (owner/admin) persists into `db.underwriting_policy` under `key=weights`.
- `compute_credit_score()` now reads weights from DB, so caps and divisors are tunable without code changes.

### Credit-score history (trajectory chart)
- `db.credit_score_snapshots` (unique on `company_id+date`) stores nightly score snapshots.
- `GET /api/credit-score/history?days=N` returns daily snapshots (default 30d, clamp 7..365). Auto-creates today's snapshot if missing so the chart always renders the latest point.
- Response: `{snapshots:[{date,score,band}], latest_score, trend, delta_period}`.
- `POST /api/credit-score/snapshot-now` (owner/admin) snapshots ALL companies; idempotent per date.
- Frontend: `cash-advance.tsx` renders a 30-bar sparkline (color-coded by band: success/brand/warning) with trend chip.

### Public Trust Score Network (Smart business enhancement)
- `GET /api/marketplace/trust-badge/{company_id}` — **public, no auth required**. Returns redacted, HMAC-signed badge: `{company_id, name, industry, score, band, verified, issued_at, signature}`.
- `POST /api/marketplace/trust-badge/verify` — public verifier; returns `{valid: bool}`.
- HMAC-SHA256 with `TRUST_SIGNING_KEY` env var (fallback: `aidou-trust-{DB_NAME}`).
- `GET /api/marketplace/businesses` now attaches `trust_badge` to every business and includes `hidden_count`. By default, businesses with score `< 600` are HIDDEN unless the user is a member or `?include_unverified=true`.
- Frontend: marketplace cards show a green/amber `VERIFIED · 820 TRUST` chip; toggle "Show unverified" reveals hidden businesses.
- Flywheel: bookings → referral inflow → score ↑ → verified badge → more bookings.

### Mocked/external integrations status
- **SendGrid** (invite emails): still MOCKED — requires `SENDGRID_API_KEY` + `SENDER_EMAIL` env vars.
- **Stripe Treasury** (cash advance disbursement): NOT STARTED — requires `STRIPE_API_KEY` + `STRIPE_TREASURY_FINANCIAL_ACCOUNT_ID`.
- **OpenAI GPT-5.2** (AI ops brief, AI chat): live via Emergent LLM key.
- **TRUST_SIGNING_KEY**: optional env var for cross-deployment signature stability.
