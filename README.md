# SchoolTrack

A school purchase and expenditure prototype for **Mwangaza Academy** (fictional),
built with FastAPI, SQLite/PostgreSQL, vanilla JavaScript and a locally bundled
Chart.js. It records purchase vouchers with multiple line items, calculates all
totals on the server, tracks approvals, manages suppliers and produces
expenditure reports and CSV exports.

**SchoolTrack is a demonstration, not a production financial system.** It has no
authentication or role permissions. Do not put real school financial or personal
data into the public demo.

![SchoolTrack dashboard](docs/dashboard.png)

![Purchase entry with live totals](docs/purchase-form.png)

![Expenditure report](docs/reports.png)

Read-only public-demo mode hides write actions and keeps the same live data:

![Read-only demonstration dashboard](docs/dashboard-readonly.png)

## Current status

- **Dual database support:** SQLite locally, PostgreSQL in deployment via the
  `DATABASE_URL` environment variable.
- **Explicit demo mode:** `DEMO_MODE` controls the warning banner, write guard and
  rate limiting. `DEMO_WRITES_ENABLED` makes a public demo interactive or
  read-only.
- **Additive migrations:** startup creates or upgrades the schema and records
  versions in `schema_migrations`; it never deletes existing data.
- **Explicit seeding:** `SEED_DEMO_DATA` seeds fiction only when the database is
  empty. Startup never repeatedly inserts demo rows.
- **Server-side money:** prices and totals are integer cents calculated on the
  server; the browser cannot inject a total or reference number.
- **KSh presentation:** the interface and CSV use Kenyan shillings (`KSh`),
  while the API also exposes the ISO code `KES`.
- **Tested locally:** 79 tests are collected; 78 pass locally against SQLite and
  1 optional PostgreSQL test is skipped when no `TEST_DATABASE_URL` is supplied.
  Real PostgreSQL execution was not possible on this machine because no
  PostgreSQL server, `psql` or Docker is installed. See limitations.

## What is implemented

| Area | Status | Where |
|---|---|---|
| Dashboard with approved expenditure, purchase count, pending approvals and recent purchases | Working | `#/dashboard` |
| Primary / Junior Secondary / All Sections filters | Working | Top bar, applied in SQL on dashboard, register and reports |
| Purchase register with search, date, status, supplier and section filters | Working | `#/purchases` |
| Purchase entry with generated reference, supplier, multiple line items, automatic totals, payment method, invoice, notes and approval status | Working | `#/purchases/new` |
| Supplier registration and purchase history | Working | `#/suppliers` |
| Approve, reject and reopen purchases | Working | Purchase detail |
| Reports by period, supplier, section and payment method | Working | `#/reports` |
| CSV export of filtered purchase records | Working | Register |
| Persistent SQLite records across restarts | Working | `data/schooltrack.db` |
| PostgreSQL deployment path | Implemented and unit-tested; real integration requires a PostgreSQL server | `DATABASE_URL` |
| Public demo warning, read-only switch, body limit and write rate limit | Working | `DEMO_*` configuration |
| Clearly labelled fictional demo data | Working | Banner, `DEMO` badges, `DEMO-` invoice numbers, CSV demo column |
| Responsive desktop/tablet/mobile layout | Working | CSS breakpoints and mobile navigation |

All dashboard figures, tables and charts come from live database queries. The
interface contains no hardcoded financial figures or fake action buttons.

## Quick start (Windows PowerShell)

The existing local database in `data/schooltrack.db` is preserved. The application
adds its migration table and indexes on first start; it does not overwrite records.

```powershell
Set-Location 'C:\Users\DELL\Documents\deepseek-harness\default-workspace\schooltrack'

# 1. Install development dependencies (runtime + pytest/httpx)
python -m pip install -r requirements-dev.txt

# 2. Create or upgrade the database schema (no seeding)
python -m app.manage init-db

# 3. Seed fictional demo data only if the database is empty
python -m app.manage seed-demo

# 4. Run the automated suite
python -m pytest

# 5. Start the local server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

Open **http://127.0.0.1:8020**. Stop with `Ctrl+C`.

The existing database already contains 19 fictional purchases and 7 suppliers, so
`seed-demo` is a no-op unless a new empty database is selected.

### Local interactive-demo mode

To exercise the exact public-demo banner, guards and rate limiter locally:

```powershell
Set-Location 'C:\Users\DELL\Documents\deepseek-harness\default-workspace\schooltrack'
$env:DEMO_MODE = 'true'
$env:DEMO_WRITES_ENABLED = 'true'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

For a read-only demo:

```powershell
$env:DEMO_MODE = 'true'
$env:DEMO_WRITES_ENABLED = 'false'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

Use `Remove-Item Env:DEMO_MODE, Env:DEMO_WRITES_ENABLED` in a new shell to return
to normal local behavior.

### Why port 8020?

Ports 8000 and 8010 were already occupied by unrelated local apps during the
original build. Port 8020 was free and is used in these instructions. Check with:

```powershell
Get-NetTCPConnection -LocalPort 8020 -State Listen
```

If it is busy, use another port such as 8022 and change the URL.

### Optional virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m app.manage init-db
python -m app.manage seed-demo
python -m pytest
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Demonstration script

Expected seeded starting figures for all sections, approved only:
**KSh 905,740.00 across 15 approved purchases**, **18 active records**, **3 pending
approvals worth KSh 90,000.00**, **1 rejected record**, **7 suppliers**, **19
fictional purchases**. Primary contributes KSh 387,540.00 and JSS KSh 518,200.00.

1. **Dashboard** — point out the demo banner, the four KPI cards, the six-month
   Primary/JSS trend and the section split. Every value comes from the API.
2. **Section selector** — switch Primary → JSS → All sections. The KPIs, charts,
   recent list and approval queue narrow to the selected section.
3. **Purchase register** — search `toner`, filter by `Pending approval`, then show
   the result count, all-status filtered total and active filter chips.
4. **CSV export** — export the filtered rows and open the file. The header uses
   `Amount (KSh)` and the `Demo record` column identifies fiction.
5. **Record a purchase** — choose *Baraka Stationers & Printers*, Primary, M-Pesa,
   invoice `DEMO-DRILL-001`; add `10 × A4 paper @ 650.00` and
   `2 × whiteboard markers @ 900.00`. The form previews **KSh 8,300.00**. Save it;
   the server issues the next reference and stores the header plus lines atomically.
6. **Approve** — confirm the approval dialog; the status and decision timestamp
   update. Return to the dashboard and show approved expenditure rising by the
   purchase amount.
7. **Reports** — choose Last 12 months, JSS, approved only; show period, supplier,
   category and payment breakdowns; use Print report.
8. **Supplier history** — open Baraka's contact card and purchase history, or
   register a new fictional supplier.
9. **Demo mode** — show the warning that public visitors share the dataset, then
   (optionally) demonstrate read-only mode by hiding write controls.

To restore the demo dataset after rehearsal, use the owner-only command described
below. Do not run it against a database containing anything you want to keep.

## Database configuration and migrations

The backend is selected automatically:

| Configuration | Backend |
|---|---|
| `DATABASE_URL` set (`postgresql://...` or `postgres://...`) | PostgreSQL |
| `DATABASE_URL` unset, `SCHOOLTRACK_DB` unset | `data/schooltrack.db` SQLite |
| `DATABASE_URL` unset, `SCHOOLTRACK_DB` set | that SQLite file |
| `DATABASE_URL=sqlite:///...` | that SQLite file (useful for tests) |

`DATABASE_URL` is read only on the server. It is never returned by the API,
logged in normal messages or embedded in HTML.

### Startup sequence

1. Open one connection using the configured backend.
2. Create `schema_migrations` if absent.
3. Apply any unapplied additive migrations, recording each version.
4. If `SEED_DEMO_DATA=true` **and** the database is completely empty, insert the
   fictional suppliers and purchases.
5. Serve requests with one request-scoped connection each.

There is no automatic deletion or truncation. Existing SQLite records are
preserved when the schema is upgraded.

### Schema

```
suppliers
  id, name (case-insensitive unique index), contact_person, phone, email,
  address, notes, is_demo, created_at

purchases
  id, reference (unique), purchase_date, supplier_id -> suppliers,
  category ('primary' | 'jss'), payment_method, invoice_number,
  status ('pending' | 'approved' | 'rejected'), notes,
  subtotal_cents, total_cents, is_demo, created_at, updated_at, decision_at

purchase_items
  id, purchase_id -> purchases (cascade), description, quantity,
  unit_cost_cents, line_total_cents, position

schema_migrations
  version, applied_at
```

- SQLite uses `AUTOINCREMENT`; PostgreSQL uses
  `GENERATED BY DEFAULT AS IDENTITY`.
- Both backends use an explicit case-insensitive `LOWER(name)` unique index.
- Foreign keys are enforced. Indexes cover date, category, status, supplier and
  line items.
- SQLite uses WAL, a busy timeout and one connection per request.
- PostgreSQL uses autocommit connections with explicit transactions; no
  connection pool is required for the single-instance free demo.

### Management commands

```powershell
python -m app.manage init-db       # schema only; never seeds
python -m app.manage seed-demo     # seed only if there are no suppliers/purchases
python -m app.manage reset-demo --yes
```

`reset-demo` is intentionally destructive and owner-controlled:

- it requires `DEMO_MODE=true`;
- it requires `ALLOW_DEMO_RESET=true`;
- it requires `--yes`;
- it deletes all purchase items, purchases and suppliers, then reseeds fiction;
- there is **no HTTP reset endpoint**.

Never leave `ALLOW_DEMO_RESET=true` enabled as a public setting. The CLI guard is
for an owner with shell/database access, not a replacement for access control.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | unset | PostgreSQL connection string. Secret. |
| `SCHOOLTRACK_DB` | `data/schooltrack.db` | SQLite file when no database URL is set. |
| `DEMO_MODE` | `false` | Enables the public-demo banner, write guard and rate limiter. |
| `DEMO_WRITES_ENABLED` | `true` in demo mode | Set `false` for a read-only demo. Outside demo mode writes are allowed for the local owner. |
| `SEED_DEMO_DATA` | `false` | Insert fictional rows only if the database is empty. |
| `MAX_REQUEST_BYTES` | `262144` | Maximum HTTP request body. |
| `RATE_LIMIT_WRITES` | `30` | Demo write attempts per client per window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window length. |
| `TRUST_PROXY_HEADERS` | `false` | Use Render's `X-Forwarded-For` for rate-limit keys. |
| `ALLOW_DEMO_RESET` | `false` | Enables only the owner CLI reset command. |
| `SCHOOLTRACK_SEED` | unset | Legacy alias for `SEED_DEMO_DATA`; prefer the new name. |

`PORT` is platform-provided on Render; do not hardcode it in the start command.
See [DEPLOYMENT.md](DEPLOYMENT.md) for the complete Render/PostgreSQL and security
checklist.

## API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Readiness plus backend/demo flags; no secrets |
| GET | `/healthz` | Alias used by some platforms |
| GET | `/api/meta` | School identity, sections, payment methods, statuses, demo flags, KSh |
| GET | `/api/dashboard?category=primary\|jss` | Live dashboard figures |
| GET | `/api/purchases` | Filters: `search`, `category`, `status`, `from`, `to`, `supplier_id`, `page`, `per_page` |
| POST | `/api/purchases` | Validate, price and persist a purchase |
| GET | `/api/purchases/{id}` | Voucher with line items |
| PATCH | `/api/purchases/{id}/status` | Approve, reject or reopen |
| GET | `/api/purchases/next-reference?purchase_date=YYYY-MM-DD` | Reference preview |
| GET | `/api/purchases/export.csv` | Filtered CSV with UTF-8 BOM |
| GET | `/api/suppliers` | Directory with aggregates; optional `search` |
| POST | `/api/suppliers` | Register a supplier |
| GET | `/api/suppliers/{id}` | Supplier plus purchase history |
| GET | `/api/reports` | `from`, `to`, `category`, `status=approved\|active` |
| GET | `/api/openapi.json` | Local OpenAPI schema |

Errors use one envelope:

```json
{"error": {"message": "Human-readable message.", "fields": {"field": "Detail"}}}
```

Validation is server-side. Unknown request fields are rejected, so a browser
cannot inject `total_cents`, `reference` or arbitrary database values.

## How money and transactions work

- Prices are validated as decimals with at most two places, converted to integer
  cents with `ROUND_HALF_UP`, multiplied by quantity and summed on the server.
- A temporary unique reference is inserted, then replaced with
  `ST-<year>-<id>` inside the same transaction. This avoids reference races on
  both SQLite and PostgreSQL.
- The purchase header and every line item are committed in one explicit
  transaction; any failure rolls the whole purchase back.
- Dashboard expenditure counts approved purchases only. The register shows all
  statuses. Reports default to approved only and can include pending records.
  Rejected records never count as expenditure.
- All category filters are applied in SQL, not filtered after retrieval.

## Automated tests

```powershell
Set-Location 'C:\Users\DELL\Documents\deepseek-harness\default-workspace\schooltrack'
python -m pytest
```

Coverage includes:

- purchase creation, sequential references, line ordering and integer-cent totals;
- rejected quantities, prices, dates, empty items, too many items and injected totals;
- approve/reject/reopen and dashboard/report updates;
- case-insensitive search, category/status/supplier/date/pagination filters;
- Primary/JSS separation;
- report grouping, averages and day/month/year periods;
- filtered CSV export with BOM and KSh/demo columns;
- supplier registration, duplicate handling, validation and history;
- persistence across restarts, idempotent migrations and transactional rollback;
- database URL selection, placeholder translation, PostgreSQL DDL shape and
  SQLite/PostgreSQL schema differences;
- demo-mode read-only enforcement, rate limiting, request-size limits, health
  output redaction and generic 500 responses;
- owner-only reset guards and absence of a reset HTTP route;
- static assets and desktop/mobile-capable shell.

The optional PostgreSQL test is skipped unless a disposable database is provided:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:5432/DATABASE_TEST?sslmode=require'
python -m pytest -m postgresql
Remove-Item Env:TEST_DATABASE_URL
```

Real PostgreSQL was not available on this machine, so that optional test is
reported as skipped rather than passed. The SQLite suite, backend-selection
tests and PostgreSQL DDL parsing were run locally.

## Project layout

```
schooltrack/
├─ app/
│  ├─ main.py           FastAPI routes, lifespan, error handlers, demo flags
│  ├─ config.py         environment configuration and demo defaults
│  ├─ db.py             SQLite/PostgreSQL adapter, schema migrations, transactions
│  ├─ security.py       headers, body limit, rate limiter, demo write guard
│  ├─ services.py       pricing, references, filters, reports, CSV
│  ├─ seed.py           fictional dataset and owner reset function
│  ├─ manage.py         init/seed/reset owner CLI
│  ├─ schemas.py        Pydantic request models
│  └─ static/           self-hosted HTML, CSS, JS and Chart.js
├─ data/schooltrack.db  local SQLite file (preserved; ignored by Git)
├─ docs/                README screenshots
├─ scripts/smoke_check.py
├─ tests/               79 collected tests
├─ requirements.txt     production/runtime dependencies
├─ requirements-dev.txt development/test dependencies
├─ render.yaml          free Render web-service blueprint (no database resource)
├─ Procfile             alternate start command
├─ .env.example         documented variables, no secrets
├─ DEPLOYMENT.md        Render, PostgreSQL and public-demo security guide
└─ pyproject.toml
```

The frontend has no build step and uses a hash router (`#/dashboard`,
`#/purchases`, etc.). Chart.js is vendored under `app/static/vendor/`; no
runtime asset is loaded from a CDN.

## Known limitations

1. **No authentication, roles or audit trail.** Approvals are status changes; any
   visitor with write access can perform them. The public demo is not a
   multi-tenant or production financial system.
2. **Public visitors share one demo dataset.** Writes are visible to everyone
   using the demo. Use read-only mode or restore the dataset after events.
3. **Rate limiting is in-memory and per process.** The free Render service runs
   one instance. Multiple workers/instances would need a shared store such as
   Redis. The limiter is casual abuse protection, not a full security boundary.
4. **No purchase editing/deleting or supplier editing.** Approvals can be reopened,
   but saved vouchers are otherwise immutable. Resetting the demo is an owner CLI
   operation.
5. **No tax, discounts, shipping or adjustments.** `subtotal` equals `total`.
   There is no budget check, purchase-order workflow, payment ledger, asset
   register or bank reconciliation.
6. **No uploads or attachments.** Receipt scans cannot be attached.
7. **KES/KSh only.** The UI shows `KSh`; the API exposes `KES`. No multi-currency.
8. **Native date-picker formatting follows the browser locale.** Tables display
   dates as `20 Oct 2026`; the date input may display `mm/dd/yyyy` in some locales.
9. **PostgreSQL was not run locally.** The implementation, portable SQL,
   placeholder translation, DDL and optional test are in place, but actual
   PostgreSQL integration must be verified against a real disposable database
   before a public launch. Do not claim it passed locally.
10. **Migrations are additive and versioned in `schema_migrations`; there is no
    automatic rollback/down migration.** Back up before future schema changes.
11. **No automated browser E2E test suite in the repository.** The interface was
    exercised manually in a headless browser during development. Re-check before
    a live demo.
12. **No student admissions, attendance, payroll or fee management.** Those areas
    are deliberately out of scope.
13. **The public demo is not for real records.** Use only fictional data; see
    DEPLOYMENT.md.

## Troubleshooting

- **Port in use:** `Get-NetTCPConnection -LocalPort 8020 -State Listen`; choose
  another port and change the URL.
- **Blank page:** confirm the server is running, then `Ctrl+F5`; check the
  browser console for a stale module.
- **PostgreSQL health check returns 503:** confirm `DATABASE_URL`, TLS mode and
  that the database accepts connections. The response intentionally omits details.
- **`psycopg` import error:** run `python -m pip install -r requirements.txt`.
- **Database locked (SQLite):** ensure only one local server is writing; WAL
  allows concurrent readers but this prototype is not a multi-writer system.
- **Permission error from PowerShell activation:** use the process-scoped
  execution policy command above.
- **Starlette/httpx warning in tests:** emitted by the dependency's TestClient and
  does not affect results.

## Deployment and manual approvals

See [DEPLOYMENT.md](DEPLOYMENT.md) for:

- external PostgreSQL setup;
- Render Blueprint and manual-service settings;
- exact environment variables and start command;
- owner-only demo restore;
- the public-demo security checklist;
- the list of manual account, billing and owner approvals.

No deployment, cloud resource, account, secret or charge was created by this
repository or by this build.
