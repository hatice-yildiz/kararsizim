# Review Checklist

Go through every section. For each item, the question is not "does the code contain X?" but "can X happen here, and what does the user experience if it does?"

## Contents
- A. Security: A1 Input · A2 Authentication · A3 Authorization · A4 Data exposure · A5 Secrets · A6 Crypto · A7 Files · A8 Config & dependencies · A9 Abuse & DoS
- B. Correctness: B1 Logic · B2 Edge cases · B3 Concurrency · B4 Error handling · B5 Data integrity · B6 Time, numbers, text · B7 State & lifecycle · B8 External calls · B9 Client-side behaviour · B10 Resources

---

## A. Security

### A1. Untrusted input
- SQL / NoSQL injection: string concatenation or f-strings building queries; raw SQL with user values; ORM `raw()`/`extra()` with interpolation.
- Command injection: user input reaching `os.system`, `subprocess(..., shell=True)`, `exec`, `eval`, template rendering of user strings.
- XSS: user content rendered without escaping (`innerHTML`, `|safe`, `mark_safe`, `dangerouslySetInnerHTML`, `v-html`); user input in `href`/`src` allowing `javascript:`.
- Path traversal: user-controlled file names or paths (`../`).
- SSRF: server fetching a URL the user supplies.
- Open redirect: `next=`/`redirect=` parameters not restricted to own domain.
- Deserialization of untrusted data (`pickle`, `yaml.load`, unsafe JSON revivers).
- Validation happening only on the client (JS) and not on the server.
- Mass assignment: binding the whole request body to a model, letting users set fields like `is_admin`, `owner_id`, `balance`.

### A2. Authentication
- Endpoints that should require login but don't.
- Passwords stored in plain text or with fast hashes (MD5, SHA1, unsalted SHA256).
- Session/token issues: no expiry, not invalidated on logout or password change, tokens in URLs or localStorage when cookies would be safer.
- Cookies missing `HttpOnly`, `Secure`, `SameSite`.
- Password reset / email verification tokens guessable, reusable or never expiring.
- Brute force: login, OTP, reset endpoints with no rate limit or lockout.
- User enumeration through different error messages ("user not found" vs "wrong password").

### A3. Authorization (most commonly missed)
- IDOR: object fetched by ID from the URL/body without checking it belongs to the current user (looking up `id` alone instead of `id` + current user/tenant).
- Checks done in the UI (hidden button) but not on the server.
- Role checks missing on admin/edit/delete actions.
- Backend-as-a-service / database access rules (e.g. PostgreSQL RLS, Firebase rules) disabled or allowing everything; a public client key used where server privileges are assumed, or a privileged key exposed to clients.
- Users able to act on behalf of others by changing a user ID in the request.
- CSRF: state-changing actions over GET, or POST endpoints with CSRF protection disabled (`csrf_exempt`).

### A4. Data exposure
- API responses returning whole objects (password hashes, emails, internal IDs, other users' data) when only a few fields are needed.
- Stack traces, SQL errors or debug pages shown to users (`DEBUG=True` in production).
- Sensitive data in logs (passwords, tokens, personal data).
- Personal data accessible to anonymous users, or in public URLs/search-indexable pages.
- Caching personalised responses publicly (CDN caching a page that contains user data).

### A5. Secrets
- API keys, DB passwords, `SECRET_KEY`, service-role keys hardcoded in code or committed config.
- Server-only secrets shipped to the browser (in JS bundles, `NEXT_PUBLIC_`/`VITE_` style public env vars, HTML).
- Default or example secrets left in place.

### A6. Cryptography & randomness
- `random`/`Math.random` used for tokens, codes, IDs that must be unguessable (use `secrets`/`crypto`).
- Home-made encryption; ECB mode; hardcoded IVs/keys.
- Comparing secrets with `==` instead of constant-time comparison (lower priority).

### A7. File handling
- Uploads: no type/size checks, files served from the same origin as executable content, original filename trusted.
- Files written to world-readable or web-served locations.

### A8. Configuration & dependencies
- CORS `*` with credentials, or overly permissive origins.
- Missing security headers where relevant (CSP, X-Frame-Options) — usually Low.
- `ALLOWED_HOSTS = ['*']`, debug toolbars in production.
- Outdated or abandoned packages with known vulnerabilities, if versions are visible.

### A9. Abuse & denial of service
- No rate limiting on actions that can be spammed (sign-up, login, sending email/SMS, creating content, expensive API calls).
- Unbounded queries: no pagination, `limit` taken from user without a maximum.
- Expensive operations (regex on user input — ReDoS, large file processing) without limits.
- N+1 queries that turn one request into thousands under real data.

---

## B. Correctness (functional bugs that hurt users)

### B1. Logic
- Conditions inverted, wrong operator (`and`/`or`, `<`/`<=`), off-by-one.
- Business rules not enforced everywhere they must be: e.g. "one coupon per customer", "no changes after an order ships", "only the owner can edit" checked in one code path but not another.
- Early returns that skip a required step (saving, notifying, releasing a lock).
- Wrong variable used (copy-paste errors), shadowed variables.
- Defaults that are wrong for the common case.

### B2. Edge cases
Trace these values explicitly through the code:
- Empty: empty string, empty list, zero items, no results from a query.
- Missing: `None`/`null`/`undefined`, missing key in dict/JSON, missing query parameter.
- Boundaries: 0, 1, negative numbers, maximum length, exactly-at-deadline.
- Unexpected types: string where number expected, list where single value expected.
- Division by zero (averages or percentages when the total is zero are a classic).
- `.get()` / `[0]` / `.first()` on something that may not exist → crash or wrong object.

### B3. Concurrency & duplicates
- Check-then-act races: "if not exists: create" or "if balance >= x: subtract" without a unique constraint, lock or atomic operation → duplicates or negative balances under concurrent requests.
- Read-modify-write on shared values (read, add 1 in code, write back) instead of an atomic update in the database or an atomic/locked operation in memory.
- Double submission: user double-clicks, network retries, browser back/resubmit → duplicate records, duplicate charges. Is the action idempotent?
- Multi-step writes without a transaction → half-finished state if step 2 fails.
- Shared mutable state (module-level globals, class attributes) in a multi-worker/serverless environment — it won't be shared between instances, and may leak between requests on the same instance.

### B4. Error handling
- Bare `except:` / `catch {}` that swallows errors → user thinks an action succeeded when it didn't.
- Errors returned as success (HTTP 200 with an error message, or no status check on a fetch).
- Missing handling for expected failures (network down, DB timeout, third-party API error).
- Partial failure leaving inconsistent data (see transactions).
- User shown a raw error or a blank page instead of a helpful message.

### B5. Data integrity
- Missing database constraints that the code relies on (uniqueness, NOT NULL, foreign keys, cascades).
- Deleting a parent leaves orphans, or cascades delete more than intended.
- Updates that overwrite other fields with stale data (lost updates).
- Soft-deleted items still appearing in some queries.
- Migrations that would fail or lose data on existing rows.

### B6. Time, numbers, text
- Time zones: naive vs aware datetimes, comparing server time to user local time, deadlines off by hours.
- Floating point for money or percentages that must add up to 100.
- Integer overflow / precision in the language used.
- Unicode/locale: locale-sensitive case conversion (e.g. Turkish dotted/dotless i), case-insensitive comparisons, sorting, string length vs bytes, emoji, text encodings when reading/writing files.
- Rounding that hides or inflates results.

### B7. State & lifecycle
- Actions allowed in the wrong state (acting on a closed, cancelled or deleted item; editing after publish).
- Caches not invalidated after updates → users see stale data.
- Session/user state assumed to exist when it may have expired.
- Pagination that skips or repeats items when data changes between pages.

### B8. External calls
- No timeout on network/DB calls → the request, job or program hangs.
- Retries without idempotency → duplicate side effects.
- Assuming third-party responses always have the expected shape.

### B9. Client-side behaviour (if front-end code is present)
- UI updated optimistically but never rolled back on server failure.
- Buttons not disabled during submission → duplicate actions.
- State that disagrees with the server after refresh.
- Forms losing user input on validation error.

### B10. Resources (any long-running code: servers, workers, CLIs, apps)
- Files, connections, sockets, locks not closed/released on every path (including errors) → leaks, exhausted pools, deadlocks.
- Unbounded growth: caches, lists or queues that never shrink; reading a whole large file into memory.
- Writing files non-atomically → a crash leaves a truncated or corrupted file; overwriting user files without a backup.
- Background tasks/threads/promises that fail silently or are never awaited.
