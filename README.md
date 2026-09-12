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

Then open http://127.0.0.1:5000 and log in with the admin account you just
created.

## Everyday use

- **Admin page** (`/admin/users`, admins only): create logins for other
  household members, deactivate accounts, reset passwords.
- **Transactions** (`/transactions`): log income/expenses, tag them, filter
  by month/category/tag. Categories (with optional monthly budgets) live at
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

## Notes

- There's no public sign-up — an admin provisions every login from the Admin
  page. The very first admin/household is created with `flask create-admin`.
- All data is scoped to a single household per login; everyone in the
  household sees and edits the same budget ("shared partner sync").
- The SQLite database lives at `instance/budgeteer.db` and is gitignored.
