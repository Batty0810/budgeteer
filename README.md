# Budgeteer

A household budget web app for tracking income and expenses, planning irregular
bills, forecasting cash flow, and managing a shared wishlist — built for a
household sharing one budget across multiple logins. Amounts are shown in
South African Rand (R).

## Stack

Flask + SQLAlchemy + SQLite, server-rendered with Jinja2, Chart.js (via CDN)
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
- **Transactions** (`/transactions`): log income/expenses, tag them, filter
  by month/category/tag. Each month shows a running balance - a "balance
  brought forward" figure (computed from your bank account and the ledger,
  or overridden manually to match a real statement at
  `/transactions/opening-balance`), a running balance per row, and a closing
  balance. Categories (with optional monthly budgets) live at
  `/transactions/categories`.
- **Dashboard** (`/`): monthly cash flow chart, category breakdown, budget
  remaining, irregular bill buffer status, and a wishlist teaser.
- **Bill Planner** (`/bills`): add annual/quarterly/irregular bills; Budgeteer
  works out the monthly amount to set aside.
- **Forecaster** (`/forecast`): set your account's current balance, add
  recurring income/expenses, and see a day-by-day projected balance 3-12
  months out.
- **Wishlist** (`/wishlist`): propose non-essential purchases, vote on them,
  and chip in savings together.

## Testing

```powershell
pip install -r requirements-dev.txt
pytest
```

Tests use an in-memory SQLite database (`config.TestConfig`) and cover the
forecasting math, auth/permission checks, and the main CRUD flows.

## Deploying to Fly.io

The app ships with a `Dockerfile`, `.dockerignore`, and `fly.toml` already set
up (gunicorn as the server, a `release_command` that runs `flask db upgrade`
on every deploy). Fly builds the image remotely, so you don't need Docker
installed locally.

```powershell
# 1. Install flyctl (one-time) - see https://fly.io/docs/flyctl/install/
iwr https://fly.io/install.ps1 -useb | iex

# 2. Log in (opens a browser)
fly auth login

# 3. Pick a globally-unique app name and update it in fly.toml, then create the app
#    (edit the `app = "budgeteer-household"` line first if you want a different name)
fly apps create budgeteer-household

# 4. Create a Postgres cluster and attach it - this sets the DATABASE_URL secret
#    for you automatically
fly postgres create --name budgeteer-db --region jnb
fly postgres attach budgeteer-db --app budgeteer-household

# 5. Set the remaining secret
fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") --app budgeteer-household

# 6. Deploy
fly deploy

# 7. Create your household's first admin login against the deployed app
fly ssh console --app budgeteer-household -C "flask create-admin --household 'Your Household' --name 'You' --email you@example.com --password 'a-strong-temp-password'"
```

After that, `fly deploy` is all you need for future updates. `fly.toml`
targets the `jnb` (Johannesburg) region as the closest to South Africa -
change `primary_region` if your household is elsewhere.

## Notes

- There's no public sign-up — an admin provisions every login from the Admin
  page. The very first admin/household is created with `flask create-admin`.
- All data is scoped to a single household per login; everyone in the
  household sees and edits the same budget ("shared partner sync").
- The SQLite database lives at `instance/budgeteer.db` and is gitignored.
