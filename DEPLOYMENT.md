# SchoolTrack deployment and public-demo guide

This guide prepares **SchoolTrack** for a Render free web service with an
external PostgreSQL database. It does not create cloud resources, accounts,
paid plans or deployments by itself. Those steps require the owner's account,
credentials and explicit approval.

> **Not for production financial records.** SchoolTrack has no authentication,
> roles, audit trail or multi-tenant isolation. It is an interactive prototype
> for fictional demonstration data only.

## What runs where

```
Browser ──HTTPS──> Render web service (Python/uvicorn)
                         │
                         └──DATABASE_URL──> PostgreSQL (external managed host)
```

- Render runs `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- The app creates/upgrades its schema on startup with an additive migration
  runner (`schema_migrations` table). Startup never deletes existing data.
- Demo rows are inserted **only** when `SEED_DEMO_DATA=true` and the database is
  completely empty. Repeated starts never duplicate demo data.
- If `DATABASE_URL` is absent, the app falls back to local SQLite. On Render
  that fallback is ephemeral and is **not suitable for the public demo**.
- The free service runs one instance. The in-memory rate limiter is therefore
  effective for this demo but is not shared across multiple instances.

## 1. Create the external PostgreSQL database (manual, owner)

Choose a free-tier PostgreSQL provider (for example Neon or Supabase), or a
Render PostgreSQL instance if the owner accepts that provider's current free
limits. The repository does not create a database.

1. Create a database named `schooltrack` and a dedicated application user.
2. Require TLS. Copy the connection string, which normally looks like:
   `postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require`
3. Keep the password in the hosting provider's secret settings; do not put it
   in `render.yaml`, README, Git or screenshots.
4. If the provider requires an IP allowlist, allow Render's outbound addresses
   or use the provider's recommended Render integration.
5. Do not point this demo at a database containing real school records.

## 2. Put the repository in a Git provider (manual, owner)

This local folder is not currently a Git repository. If deploying:

```powershell
Set-Location 'C:\Users\DELL\Documents\deepseek-harness\default-workspace\schooltrack'
git init
git add .
git commit -m "SchoolTrack dual-backend public demo"
# Create an empty repository in GitHub/GitLab, then:
git remote add origin <YOUR_REPOSITORY_URL>
git push -u origin main
```

The included `.gitignore` excludes local databases, `.env`, caches and virtual
environments. Never commit `data/schooltrack.db` or credentials.

## 3. Deploy on Render

### Option A — Blueprint (`render.yaml`)

1. In Render, choose **New → Blueprint**.
2. Connect the repository.
3. Render reads `render.yaml` and proposes one **free** web service named
   `schooltrack-demo`. Confirm there is no paid database or add-on in the plan.
4. Set the `DATABASE_URL` secret to the external PostgreSQL connection string.
5. Apply/deploy.
6. Confirm the health check passes at `/api/health`.

### Option B — Manual web service

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Plan | Free |
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |
| Persistent disk | Not required (data is in PostgreSQL) |

Add the environment variables from the table below. `PORT` is set by Render;
do not hardcode it.

## 4. Environment variables

| Variable | Required on Render | Example | Meaning |
|---|---|---|---|
| `DATABASE_URL` | **Yes** for public demo | `postgresql://...?...sslmode=require` | PostgreSQL connection string. Secret. |
| `DEMO_MODE` | **Yes** | `true` | Enables the public-demo banner, write guard and rate limiting. |
| `DEMO_WRITES_ENABLED` | Yes | `true` or `false` | `true` lets visitors create/approve; `false` makes the whole demo read-only. |
| `SEED_DEMO_DATA` | First deploy | `true` | Seeds fiction only if the database is empty. Set `false` later if preferred. |
| `TRUST_PROXY_HEADERS` | Yes on Render | `true` | Uses Render's `X-Forwarded-For` for rate-limit keys. |
| `MAX_REQUEST_BYTES` | Optional | `262144` | Hard request-body cap (256 KiB default). |
| `RATE_LIMIT_WRITES` | Optional | `30` | Write requests allowed per client/window. |
| `RATE_LIMIT_WINDOW_SECONDS` | Optional | `60` | Rate-limit window length. |
| `ALLOW_DEMO_RESET` | No | `false` | Only enables the owner CLI reset; there is no HTTP reset route. |
| `SCHOOLTRACK_DB` | No | `data/schooltrack.db` | Local SQLite fallback when `DATABASE_URL` is unset. |
| `PYTHON_VERSION` | Optional | `3.12.8` | Render's Python version hint. |

The recommended public-demo settings are in `render.yaml`:

```yaml
DEMO_MODE=true
DEMO_WRITES_ENABLED=true
SEED_DEMO_DATA=true
TRUST_PROXY_HEADERS=true
DATABASE_URL=<set as a secret in Render>
```

If the public demo should be read-only, set `DEMO_WRITES_ENABLED=false`. The UI
hides purchase/register/approval controls and the API returns `403` for writes.

## 5. First boot and verification

The app initializes the schema automatically. On the first boot with
`SEED_DEMO_DATA=true` and an empty database, it inserts the fictional dataset.

Verify:

```powershell
# Replace with the deployed URL.
Invoke-RestMethod 'https://YOUR-SERVICE.onrender.com/api/health'
Invoke-RestMethod 'https://YOUR-SERVICE.onrender.com/api/meta'
```

Expected health shape:

```json
{
  "status": "ok",
  "ready": true,
  "app": "SchoolTrack",
  "version": "1.1.0",
  "database": "postgresql",
  "demo_mode": true,
  "writes_enabled": true
}
```

No database host, username, password or connection string is returned.

Check in a private browser:

1. The demo banner warns that data is fictional and visitors share it.
2. The dashboard totals match the seeded demo dataset.
3. A test supplier/purchase can be created if writes are enabled; approve it.
4. The register filters, supplier history, reports and CSV export work.
5. `/api/health` returns `200`.
6. A direct `POST /api/admin/reset` returns `404`.
7. A burst of writes eventually returns `429` with `Retry-After`.

## 6. Restoring the shared demo dataset (owner only)

Public visitors share the same database. There is **no HTTP reset endpoint**.
Restore is an owner-run CLI command that refuses to run unless the environment
explicitly allows it.

From a trusted machine with the deployment's database URL:

```powershell
Set-Location 'C:\Users\DELL\Documents\deepseek-harness\default-workspace\schooltrack'

# Point at the deployment database. Use a temporary shell; never commit this.
$env:DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require'
$env:DEMO_MODE = 'true'
$env:ALLOW_DEMO_RESET = 'true'

# Destructive: removes ALL purchases and suppliers, then reseeds fiction.
python -m app.manage reset-demo --yes

Remove-Item Env:DATABASE_URL, Env:DEMO_MODE, Env:ALLOW_DEMO_RESET
```

`reset-demo` also requires `--yes`. It does not drop the schema and never runs
automatically. If Render Shell is unavailable on the chosen plan, run this from
a trusted local machine that can reach the database, or use the provider's SQL
console with a reviewed backup/restore process.

Do not enable `ALLOW_DEMO_RESET` as a long-lived public setting; it only guards a
CLI action that someone with database/shell access can already perform.

## 7. Public-demo security checklist

- [ ] `DEMO_MODE=true` so the warning banner and guards are active.
- [ ] `DEMO_WRITES_ENABLED` intentionally set; read-only if the owner does not
      want visitors changing the shared dataset.
- [ ] `DATABASE_URL` is a secret, uses TLS (`sslmode=require`), and has a
      dedicated least-privilege database user.
- [ ] No credentials, `.env`, local SQLite database or real school records are
      committed or included in screenshots.
- [ ] `SEED_DEMO_DATA=true` only for the fictional demo; never for real records.
- [ ] `/api/health` returns `200` and exposes no configuration details.
- [ ] Rate limiting is enabled (`RATE_LIMIT_WRITES`, window) and the service is
      running a single instance, matching the in-memory limiter design.
- [ ] `MAX_REQUEST_BYTES` is set to a reasonable cap.
- [ ] CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` and
      `Permissions-Policy` headers are present.
- [ ] There is no upload endpoint, no arbitrary file serving and no reset route.
- [ ] The owner knows that visitors share one dataset and can create/approve
      fictional records if writes are enabled.
- [ ] The owner accepts that this is not a production financial system, has no
      authentication and must not hold real financial or personal data.
- [ ] Database backups/retention are configured by the owner if desired; the
      application does not automate them.
- [ ] Owner has approved any free-tier limits, account creation and deployment.

## 8. Local PostgreSQL verification

The repository includes an optional integration test. It is skipped unless a
disposable database URL is supplied:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:5432/DATABASE_TEST?sslmode=require'
python -m pytest -m postgresql
Remove-Item Env:TEST_DATABASE_URL
```

Only point this at a disposable test database. It creates suppliers and
purchases and does not delete them automatically.

If PostgreSQL is unavailable locally, the normal SQLite suite plus the
backend-selection, SQL-shape and migration tests still run. Real PostgreSQL
behavior must be confirmed against the deployment database; do not claim it
was verified locally when it was not.

## 9. What still requires manual owner action

- Creating/owning a Render account and approving the free plan.
- Creating the external PostgreSQL account/database and storing its secret.
- Creating or connecting the Git repository.
- Triggering the deployment and any custom domain/DNS changes.
- Deciding whether the public demo is writable or read-only.
- Restoring the shared demo dataset after public use.
- Any backup, retention or billing decision.
- Legal/privacy review before publishing any demo URL.

No deployment, cloud resource, account or charge was created during this work.
