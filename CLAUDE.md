# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Kararsızım** is a Django 5.2 / Python 3.12 poll app (users ask others to help them decide, 2–5 options per poll). The single source of truth is [docs/KARARSIZIM_PLAN.md](docs/KARARSIZIM_PLAN.md) (in Turkish): data model, URLs, UI rules, and the phase breakdown. Implement phases **one at a time, in order**, and stop for user review after each phase. Phases 1–2 (setup, accounts) are done; Phase 3 (polls) is next.

## Commands

Use the project venv (`.venv`, Python 3.12):

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py makemigrations && .venv/bin/python manage.py migrate
DATABASE_URL= .venv/bin/python manage.py test                       # all tests
DATABASE_URL= .venv/bin/python manage.py test accounts.tests.RegisterTests.test_password_mismatch   # single test
.venv/bin/python manage.py check
```

**Always run tests with `DATABASE_URL=` (empty).** `.env` points at the real Supabase database; without the override, Django tries to create a `test_postgres` database on Supabase and fails (and leaves junk behind). The empty override makes tests use SQLite. No linter is configured.

## Environment / database

- Config comes from `.env` (gitignored; template in `.env.example`) via python-dotenv. `config/settings.py` uses `DATABASE_URL` if set (Supabase PostgreSQL via dj-database-url, `CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS`, SSL required), otherwise falls back to local `db.sqlite3`.
- Because `.env` has `DATABASE_URL`, `runserver`/`migrate` hit the **real Supabase DB** by default. Prefix with `DATABASE_URL=` to use SQLite instead.
- Supabase pooler host is `aws-1-eu-central-1.pooler.supabase.com` (not `aws-0`); migrations use the Session pooler (port 5432), the deployed app should use the Transaction pooler (6543). Supabase Auth / supabase-py are deliberately not used — Django auth only.
- Only the packages in `requirements.txt` are allowed; justify any addition (see plan §2). No CSS/JS frameworks — plain HTML/CSS/JS in Django templates.
- User-facing text is Turkish; code identifiers are English. Validation is always server-side.

## Architecture

- `config/` — settings, root URLs (all routes are wired in `config/urls.py`, there are no per-app urls modules yet), WSGI (`app = application` is required for Vercel).
- `accounts/` — custom `User` (`AUTH_USER_MODEL`): **login is by email** (`USERNAME_FIELD = "email"`), `username` is a separate display name. Email is lowercased in `save()`, and username/email uniqueness is case-insensitive via `Lower()` unique constraints plus checks in `RegisterForm`. `accounts.backends.EmailBackend` handles email+password auth. `first_name`/`last_name` are removed. Email must never be rendered in any template (tests assert this).
- `polls/` — currently only a placeholder `home` view; models (`Poll`, `Option`, `Vote`) are specified in plan §5.2–5.4. Anonymous votes are tracked by a `voter_id` cookie (middleware to be written in Phase 4), members by user id, via `Vote.voter_key` + unique `(poll, voter_key)`.
- `templates/base.html` holds the navbar (state-dependent on login) and the `messages` block; `static/` is served by WhiteNoise. `static/css/style.css` is a minimal placeholder until Phase 5 applies the design system from plan §8.
