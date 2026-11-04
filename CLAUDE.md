# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Kararsızım** is a Django 5.2 / Python 3.12 poll app (users ask others to help them decide, 2–5 options per poll). The single source of truth is [docs/KARARSIZIM_PLAN.md](docs/KARARSIZIM_PLAN.md) (in Turkish): data model, URLs, UI rules, and the phase breakdown. Implement phases **one at a time, in order**, and stop for user review after each phase. Phases 1–6 are implemented (setup, accounts, polls, voting, UI design, Vercel prep); the remaining step is the actual Vercel deploy (see README).

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
- `DEBUG` defaults to **False**; with it off, `SECRET_KEY` is required (settings raise otherwise, except under `manage.py test`). `.env` sets `DEBUG=True` locally.
- Dependencies live in both `requirements.txt` and `pyproject.toml` (Vercel may read either) — keep them identical. Only the packages listed there are allowed; justify any addition (see plan §2). No CSS/JS frameworks — plain HTML/CSS/JS in Django templates.
- User-facing text is Turkish; code identifiers are English. Validation is always server-side.

## Architecture

- `config/` — settings, root URLs (all routes are wired in `config/urls.py`, there are no per-app urls modules yet), WSGI (`app = application` is required for Vercel).
- `accounts/` — custom `User` (`AUTH_USER_MODEL`): **login accepts email or username** (`USERNAME_FIELD = "email"`; the backend treats a value containing `@` as email, otherwise as username, both case-insensitive), `username` is also the public display name. Email is lowercased in `save()`, and username/email uniqueness is case-insensitive via `Lower()` unique constraints plus checks in `RegisterForm`. `accounts.backends.EmailBackend` handles email-or-username + password auth. `first_name`/`last_name` are removed. Email must never be rendered in any template (tests assert this).
- `polls/` — `Poll`, `Option`, `Vote`. One vote per voter per poll is enforced by `Vote.voter_key` (`u:<user id>` for members, `a:<uuid>` for guests, see `polls/voting.py`) plus a unique `(poll, voter_key)` constraint; `polls.middleware.VoterCookieMiddleware` issues the guest `voter_id` cookie and sets `request.voter_id`. `poll_vote` validates that the option belongs to the poll and relies on the DB constraint for race-safe duplicate rejection. Poll querysets that use `annotate()` must call `.order_by(...)` explicitly (annotate drops `Meta.ordering`, which breaks pagination). Poll creation uses a plain `PollForm` with fixed `option_1..option_5` fields; `static/js/poll_form.js` only shows/hides rows.
- `templates/base.html` holds the navbar (state-dependent on login) and the `messages` block. `static/css/style.css` is the full design system from plan §8 (CSS variables, option colours `--c1..--c5`, animated result bars); `404.html`/`500.html` are custom (500 is standalone, no context).
- Deployment: Vercel auto-detects Django via `manage.py` (no `vercel.json`), runs `collectstatic` itself and serves static files from its CDN; `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` are extended from Vercel's `VERCEL_*` system env vars. Migrations are run locally, never in the Vercel build.
- `polls/migrations/0003_enable_rls.py` enables Row Level Security on every public table (Supabase exposes `public` through its REST API). It only covers tables that existed then — **any new model needs its own RLS migration**.
