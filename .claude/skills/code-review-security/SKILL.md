---
name: code-review-security
description: Thorough review of code for anything that could hurt users - security holes (injection, broken auth/authorization, data leaks, secrets) AND functional bugs that make features behave wrongly (logic errors, race conditions, bad edge-case handling, data loss, wrong calculations). Language and framework agnostic. Use whenever the user asks to review, audit or check code for security or correctness - e.g. "bu kodu güvenlik açısından incele", "kodda açık var mı", "bu fonksiyon doğru çalışıyor mu", "code review yap", "security review", "is this safe", "find bugs in this" - even if they only say "incele" or "kontrol et" about a piece of code. Produces a severity-ranked report with fixes.
---

# Code Review: Security + Correctness

The goal is to protect the people who use the software. A user can be harmed in two ways, and this review treats both as first-class:

1. **Security** – an attacker can read, change or destroy data they shouldn't, impersonate someone, or take down the service.
2. **Correctness** – no attacker needed: the feature simply does the wrong thing (an order is created twice, a balance drifts, a deleted item reappears, a user sees someone else's data because of a caching bug, an error is swallowed and data is silently lost, a file is half-written when the process crashes).

Reviewers tend to fixate on the first and skim the second. Many of the bugs that actually hurt users in production are the second kind, so give them equal attention.

## When this runs

Only when the user asks for a review. Don't run it unprompted while writing code.

## Any language, any kind of project

This skill is meant to be reused on every project, so don't assume a stack. Identify the language, framework and kind of software from the code itself (web backend, frontend, mobile app, CLI tool, library, background job, infrastructure/config) and adapt:
- Apply the checklist categories that fit and skip the ones that don't (a CLI tool has no CSRF; a library has no sessions, but its callers may misuse its API).
- Judge "the user" broadly: the end user of an app, the operator running a script, or the developer calling a library.
- Write fixes with the idioms and built-in protections of *that* language and framework, not a generic or different one.

## Process

### 1. Understand before judging
Before listing problems, work out:
- What the code is supposed to do (from names, comments, the user's description). If intent is genuinely unclear and it changes the verdict, say what you assumed.
- **Trust boundaries**: where does data come from (HTTP request, form, URL, file upload, database, third-party API, env)? Anything that crosses from outside is untrusted until validated.
- **Who calls this and who should be allowed to**: anonymous visitor, logged-in user, owner of the resource, admin.
- **What state it touches**: database rows, files, caches, money, counters, external services.

If the user gave only a fragment, review it, but flag where the verdict depends on code you can't see ("if `get_record` doesn't check ownership, this is an IDOR") rather than guessing silently. If you can read the surrounding files, do so.

### 2. Walk the checklist
Read `references/checklist.md` and go through every category against the code. It is organised as:
- A. Security (input handling, authn/authz, data exposure, secrets, crypto, dependencies, config, abuse/DoS)
- B. Correctness (logic, edge cases, concurrency, error handling, data integrity, time/numbers/text, state & lifecycle, external calls)

Don't just pattern-match keywords. For each piece of code, ask "what input or sequence of events makes this misbehave, and what does the user experience when it does?" Trace concrete values through the code — an empty list, `None`/`null`, a negative number, a huge string, two requests at the same instant, the same request sent twice, a user who isn't the owner.

### 3. Verify each finding
Before reporting, check the finding is real:
- Is there mitigation elsewhere you can see (framework auto-escaping, ORM parameterisation, a decorator, a DB constraint)? If so, drop it or downgrade it.
- Can you describe a concrete scenario (input → what happens → impact on the user)? If you can't, it's probably a style note, not a finding.

- Is the location right? Users jump straight to the cited line, and line numbers counted by eye are often off by a few. Read the file with line numbers shown (e.g. `grep -n`, `cat -n`, or a read tool that numbers lines) and confirm every `file:line` in the report against it before finishing. If you only have a pasted snippet without line numbers, cite the function name instead.

False positives erode trust in the review; a short list of real problems beats a long list padded with theory. Pure style issues (naming, formatting) don't belong in this report.

### 4. Assign severity by impact on users
- **Kritik / Critical** – exploitable now with little effort, or guaranteed to corrupt/leak data: SQL injection, auth bypass, accessing other users' data, hardcoded production secrets, remote code execution, money, balances or counts miscounted for everyone.
- **Yüksek / High** – serious harm but needs some condition: stored XSS, CSRF on state-changing actions, race condition that duplicates records under normal load, unhandled error that loses user data.
- **Orta / Medium** – limited impact or harder to trigger: missing rate limit, verbose error messages leaking internals, edge case that breaks one feature for some users.
- **Düşük / Low** – defence-in-depth, hardening, minor UX-affecting bugs.

When unsure between two levels, choose based on how many users are affected and whether the damage is reversible.

## Report format

Write the report in the user's language (Turkish if they write in Turkish). Use this structure:

```
# Güvenlik ve Doğruluk İncelemesi: <what was reviewed>

## Özet
<2-4 sentences: overall state, number of findings per severity, the single most urgent thing to fix.>

| # | Önem | Tür | Başlık | Konum |
|---|------|-----|--------|-------|
| 1 | Kritik | Güvenlik | ... | file.py:42 |
| 2 | Yüksek | İşlevsel | ... | file.py:88 |

## Bulgular

### 1. [Kritik] <short title>
**Tür:** Güvenlik | İşlevsel
**Konum:** `file:line` (function name)
**Sorun:** What is wrong, in plain words.
**Senaryo:** A concrete step-by-step example of how it goes wrong (the input, the request, the timing).
**Kullanıcıya etkisi:** What the end user experiences or loses.
**Düzeltme:**
<minimal corrected code, in the same language/framework as the original>
<one line on why this fixes it>

(repeat, ordered Kritik → Yüksek → Orta → Düşük)

## Doğru yapılanlar
<Brief bullets of things done well, so the user knows what to keep. Skip if nothing notable.>

## Kontrol edilemeyenler
<What you couldn't verify without more code/config, and what to check. Skip if none.>
```

If nothing serious is found, say so plainly and still list what was checked — "no findings" is a valid, useful result; don't invent problems to fill the report.

## Fixes

Keep fixes minimal and in the code's own style and framework — the user should be able to paste them in. Prefer the platform's built-in protections (parameterised queries, the framework's CSRF and escaping features, database transactions, row locks or atomic updates, unique constraints, the standard library's secure random and password hashing) over hand-rolled code. If a fix needs a schema change or migration, say so.
