# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Tahmince** ("Tahminini yap, sonucu gör!") is a Django 5.2 / Python 3.12 prediction app: members open questions about future outcomes (2–4 choices, category, closing time), other members predict, the creator reports the result after closing and correct predictors get 10 points. It was converted from the earlier poll app "Kararsızım" (still in the repo as read-only legacy data). [docs/KARARSIZIM_PLAN.md](docs/KARARSIZIM_PLAN.md) is the original plan of the old poll app (historical). Do **not** apply migrations to the production Supabase DB or deploy/push `main` (auto-deploys to Vercel) without showing the user the changes first. Phases 1–6 are implemented (setup, accounts, polls, voting, UI design, Vercel prep); the remaining step is the actual Vercel deploy (see README).

## Commands

Use the project venv (`.venv`, Python 3.12):

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py makemigrations && .venv/bin/python manage.py migrate
DATABASE_URL= .venv/bin/python manage.py test                       # all tests (SQLite)
DATABASE_URL=postgresql://user@localhost:5432/postgres .venv/bin/python manage.py test   # incl. trigger tests (needs a LOCAL PostgreSQL, never production)
DATABASE_URL= .venv/bin/python manage.py seed_demo                  # local demo data (DEBUG + SQLite only)
DATABASE_URL= .venv/bin/python manage.py test accounts.tests.RegisterTests.test_password_mismatch   # single test
.venv/bin/python manage.py check
```

**Always run tests with `DATABASE_URL=` (empty).** `.env` points at the real Supabase database; without the override, Django tries to create a `test_postgres` database on Supabase and fails (and leaves junk behind). The empty override makes tests use SQLite. No linter is configured.

## Environment / database

- Config comes from `.env` (gitignored; template in `.env.example`) via python-dotenv. `config/settings.py` uses `DATABASE_URL` if set (Supabase PostgreSQL via dj-database-url, `CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS`, SSL required), otherwise falls back to local `db.sqlite3`.
- Because `.env` has `DATABASE_URL`, `runserver`/`migrate` hit the **real Supabase DB** by default. Prefix with `DATABASE_URL=` to use SQLite instead.
- Supabase pooler host is `aws-1-eu-central-1.pooler.supabase.com` (not `aws-0`); migrations use the Session pooler (port 5432), the deployed app should use the Transaction pooler (6543). Supabase Auth / supabase-py are deliberately not used — Django auth only.
- `DEBUG` defaults to **False**; with it off, `SECRET_KEY` is required (settings raise otherwise, except under `manage.py test`). `.env` sets `DEBUG=True` locally.
- Dependencies live in both `requirements.txt` and `pyproject.toml` (Vercel may read either) — keep them identical. Only the packages listed there are allowed; justify any addition (see plan §2). No CSS/JS frameworks — plain HTML/CSS/JS in Django templates.
- User-facing text is Turkish; code identifiers are English. Validation is always server-side.

## Architecture

- `config/` — settings, root URLs (all routes are wired in `config/urls.py`, there are no per-app urls modules yet), WSGI (`app = application` is required for Vercel).
- `accounts/` — custom `User` (`AUTH_USER_MODEL`): **login accepts email or username** (`USERNAME_FIELD = "email"`; the backend treats a value containing `@` as email, otherwise as username, both case-insensitive), `username` is also the public display name. Email is lowercased in `save()`, and username/email uniqueness is case-insensitive via `Lower()` unique constraints plus checks in `RegisterForm`. `accounts.backends.EmailBackend` handles email-or-username + password auth. `first_name`/`last_name` are removed. Email must never be rendered in any template (tests assert this).
- `predictions/` — the product. `Question` (title, description, resolution_criteria, category, `closes_at` stored UTC, `status` = open/resolved/cancelled, result fields), `Choice` (2–4), `Prediction` (unique per question+user, `is_correct`/`points_awarded` written once at resolution). **"Sonuç bekliyor" is not stored**: it is `status=open` and `closes_at <= now`, derived in `Question.display_status` / `QuestionQuerySet` (`accepting/awaiting/finished`), so no cron is needed. All writes go through `predictions/services.py` (single transaction + `select_for_update` on the question); resolution is one conditional `UPDATE ... WHERE status='open' AND closes_at<=now` and points are written only by the call that wins it — never write points anywhere else. `migrations/0002_db_guards.py` adds PostgreSQL triggers (closing, own-question, locked fields, immutable result, one-time points) and enables RLS on every public table; it is a no-op on SQLite, so trigger behaviour is only covered by `predictions/tests_postgres.py` (skipped on SQLite, needs a real PostgreSQL). Any new table needs its own RLS statement. Times: stored UTC, rendered with `|iso_utc` (`templatetags/tahmince.py`) and converted to the viewer's local time by `static/js/main.js`; do **not** use Django's `date:"c"`/`P` for machine-readable dates.
- `polls/` — legacy "Kararsızım" polls kept as a **read-only archive** (`/eski-anketler/`): models/migrations/data untouched, no voting/creating/deleting, no voter cookie. Never convert old votes into points.
- `templates/base.html` holds the navbar, metadata (title/description/og tags) and the `messages` block. `static/css/style.css` is the dark navy/purple/green design system (CSS variables, `choice-c1..c5` option colours, animated distribution bars); `static/js/main.js` does local-time conversion, countdowns, auto-hiding messages and the form loading state; `static/js/question_form.js` handles the choice rows and sends the closing time as UTC. `404.html`/`500.html` are custom (500 is standalone, no context).
- Deployment: Vercel auto-detects Django via `manage.py` (no `vercel.json`), runs `collectstatic` itself and serves static files from its CDN; `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` are extended from Vercel's `VERCEL_*` system env vars. Migrations are run locally, never in the Vercel build.
- `polls/migrations/0003_enable_rls.py` and `predictions/migrations/0002_db_guards.py` enable Row Level Security on every public table (Supabase exposes `public` through its REST API). It only covers tables that existed then — **any new model needs its own RLS migration**.
