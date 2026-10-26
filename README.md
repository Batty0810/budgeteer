# Budgeteer

A household budget web app for tracking income and expenses, planning irregular
bills, forecasting cash flow, and managing a shared wishlist — built for a
household sharing one budget across multiple logins. Amounts are shown in
South African Rand (R).

## Stack

Flask + SQLAlchemy (SQLite locally, Postgres when deployed), server-rendered with Jinja2, Chart.js (via CDN)
for charts. No Node.js/npm required to run it.

## Setup

```powershell
# 1. Create and activate a virtual environment
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# edit .env and set a real SECRET_KEY

# 4. Set up the database
flask db init
flask db migrate -m "Initial schema"
flask db upgrade

# 5. Create your household and the first admin login
flask create-admin

# 6. Run it
flask run
```

Then open http://127.0.0.1:5030 and log in with the admin account you just
created.

## Everyday use

- **Admin page** (`/admin/users`, admins only): create logins for other
  household members, deactivate accounts, reset passwords.
- **Budget periods**: by default the Dashboard and Transactions pages report
  on calendar months. If you're paid on, say, the 25th, set "Budget month
  starts on day" to 25 under Admin -> Household, and both pages switch to
  25th-to-24th periods, so the salary and the bills it pays fall in the same
  period. The arrows step one period at a time, and the From/To boxes show
  any custom date range.
- **Transactions** (`/transactions`): log income/expenses, tag them, filter
  by period/category/tag/who logged it. Each period shows a running balance -
  a "balance brought forward" figure (computed from your bank account and
  the ledger, or overridden manually to match a real statement at
  `/transactions/opening-balance`), a running balance per row, and a closing
  balance. Categories (with optional monthly budgets) live at
  `/transactions/categories`.
- **Dashboard** (`/`): monthly cash flow chart, category breakdown, a
  "by household member" breakdown of who's bringing in and spending what,
  budget remaining, irregular bill buffer status, and a wishlist teaser.
- **Bill Planner** (`/bills`): add annual/quarterly/irregular bills; Budgeteer
  works out the monthly amount to set aside.
- **Forecaster** (`/forecast`): set your account's current balance, add
  recurring income/expenses, and see a day-by-day projected balance 3-12
  months out.
- **Wishlist** (`/wishlist`): propose non-essential purchases, vote on them,
  and chip in savings together.
- **Import from PDF** (`/imports/upload`, linked from Transactions): upload a
  bank statement PDF (optionally password-protected) and Budgeteer extracts
  candidate transactions - date, description, amount, income/expense, and a
  best-guess category. Nothing is saved until you review and edit the list
  (fix amounts/categories, untick anything wrong, add tags) and confirm; you
  can also flag any row as recurring (with a frequency) to seed the
  forecaster, and optionally apply the statement's opening balance as that
  month's "balance brought forward". Statement layouts vary a lot between
  banks, so treat the extraction as a head start, not a guarantee.

## Testing

```powershell
pip install -r requirements-dev.txt
pytest
```

Tests use an in-memory SQLite database (`config.TestConfig`) and cover the
forecasting math, auth/permission checks, and the main CRUD flows.

## Deploying (free: GitHub + Render + Neon)

The live site runs entirely on free tiers, straight from this GitHub repo:

- **GitHub** holds the code and runs the tests on every push
  (`.github/workflows/tests.yml`).
- **Render** (free web service) runs the app. `render.yaml` describes it, and
  every push to `main` redeploys automatically once the tests pass.
  Migrations (`flask db upgrade`) run each time the app starts.
- **Neon** (free Postgres) holds the data. Unlike Render's own free database,
  it doesn't expire.

The one trade-off: Render's free tier puts the app to sleep after 15 minutes
of no visits, so the first visit after a quiet spell takes up to about a
minute to load. After that it's normal speed.

### One-time setup

**1. Create the database on Neon.** Sign up at https://neon.tech (logging in
with GitHub is fine), create a project, and pick the **AWS Europe Central
(Frankfurt)** region so it sits next to the app. On the project dashboard,
click **Connect**, turn **Connection pooling** off, and copy the connection
string (`postgresql://...neon.tech/neondb?sslmode=require...`).

**2. Create your admin login.** Render's free tier has no remote shell, so
run this once from your own machine, pointing at the Neon database:

```powershell
.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql://...paste the Neon string..."
flask db upgrade
flask create-admin
Remove-Item Env:DATABASE_URL   # back to your local SQLite database
```

**3. Create the app on Render.** Sign up at https://render.com with GitHub,
then **New -> Blueprint**, pick this repository, and paste the same Neon
connection string when it asks for `DATABASE_URL`. `SECRET_KEY` is generated
for you. Click **Apply**. The first deploy takes a few minutes, and then the
app is live at `https://budgeteer-<something>.onrender.com`. Log in with the
admin account from step 2, and add the other household members from the
Admin page.

Tip: on a phone, open the site and choose "Add to Home Screen" for
one-tap access.

### Updating

Push to `main`. GitHub runs the tests, and Render deploys when they pass.
You can follow progress in the repo's Actions tab and on the Render dashboard.

## Notes

- There's no public sign-up — an admin provisions every login from the Admin
  page. The very first admin/household is created with `flask create-admin`.
- All data is scoped to a single household per login; everyone in the
  household sees and edits the same budget ("shared partner sync").
- Locally, the SQLite database lives at `instance/budgeteer.db` and is
  gitignored. The deployed site uses Neon Postgres via `DATABASE_URL`.
