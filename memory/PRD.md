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
