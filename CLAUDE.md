# CLAUDE.md

Project instructions for Claude Code. Read this fully before writing any code.

---

## 1. What this is

**JobFit** — a job application tracker with AI fit-scoring.

This is a capstone submission for the **FlyRank Internship, Backend Track**, under the brief
*"Your 10x Solution."* The brief is the source of truth for what counts as done. A working
system that satisfies the brief beats an impressive system that drifts from it.

### The problem

Applying to jobs at volume is mostly reading, not applying. A candidate opens twenty postings a
week and mentally checks each against their own CV — years, stack, seniority, location. Most
postings fail on one line buried in the middle, so the reading is almost entirely wasted.

The second half is memory: after thirty applications across LinkedIn, career pages, and email
referrals, you no longer know which are live, which went silent, and which you never followed up on.

**Who has it:** final-year students and early-career developers running an active job search,
applying to 10–30 roles a month, with no recruiter and no ATS of their own.

### The 10x claim

> Deciding whether a posting is worth applying to took 15 minutes of careful reading.
> It now takes 20 seconds of reading a score and three bullet points.

### The non-goal — defend this

**We do NOT build auto-apply or form-filling.** No submitting applications on the user's behalf,
no browser automation into third-party ATS systems. The system advises and tracks; the human applies.

Secondary non-goal: **not a multi-user SaaS.** Auth exists because the brief requires protected
routes and the data is personal, but the product assumes one user per deployment.

---

## 2. Hard constraints — never violate these

These come from the capstone brief. Breaking any of them breaks the submission.

| Constraint | What it means in practice |
|---|---|
| **$0 stack, no credit card** | Free tiers, local services, test modes only. If a chosen service starts demanding a card, swap it — do not pay. |
| **No secrets in Git** | Keys and passwords live in env vars only. Never commit. Never log them, not even at DEBUG. `.env` is gitignored from commit one. |
| **No other people's personal data** | Use the developer's own CV, self-written postings, or public sources. No scraped applicant data, no third-party résumés. |
| **Understand every line** | AI assistance is allowed and encouraged, but the author must be able to explain any file. Prefer boring, readable code over clever code. |
| **Scope guard** | The core feature list is capped at 5. It is frozen (section 3). Do not add a sixth. |
| **Buildable in ~3 weeks part-time** | When a choice appears between "correct and large" and "correct and small," take small. |

When a shiny idea appears mid-build, write it in `README.md` under **Future ideas** and return to
the current milestone. Do not build it.

---

## 3. Core feature list — FROZEN at 5

1. **Ingest a posting** — by pasted text (primary) or URL (convenience).
2. **Extract structured requirements** — title, company, seniority, skills, years, location/remote.
3. **Score against the stored CV profile** — 0–100 plus a short rationale.
4. **Track application state** — saved → applied → interviewing → rejected/ghosted, with timestamps.
5. **Weekly PDF digest, emailed on a schedule** — new high scores and stale applications.

Anything else (browser extension, Slack bot, salary analytics, cover-letter generation) →
**Future ideas** in the README. Not built.

---

## 4. Concept coverage — the grading rule

The brief requires **at least 5 of 7 program concepts**, with a **maximum of 2 swaps**. This project
implements **all 7 with ZERO swaps**. That is deliberate: nothing to justify, and slack if one
concept fights us.

| # | Concept | How it is satisfied | Lives in |
|---|---|---|---|
| 1 | **API endpoints** | REST API with correct status codes; Pydantic request/response validation; 422 on bad input, 404 on missing, 409 on duplicate | `api/app/routers/` |
| 2 | **Database** | Supabase Postgres; data survives restart; Alembic migrations under version control | `api/app/models/`, `api/migrations/` |
| 3 | **Authentication** | JWT login; every `/jobs`, `/profile`, `/applications` route protected; ownership checked on every row | `api/app/auth/` |
| 4 | **Background jobs + cron** | RQ worker scores postings off the request path; rq-scheduler fires the weekly digest | `api/app/workers/` |
| 5 | **Reporting (PDF + email)** | Weekly digest rendered to PDF and emailed; also downloadable on demand | `api/app/reports/` |
| 6 | **Caching** | Posting content + extraction cached in Redis by URL/text hash; identical re-ingest returns cached result with **no LLM call** | `api/app/cache/` |
| 7 | **LLM integration** | One narrow job: posting text → strict JSON of requirements + fit score. Schema-validated, one repair retry, **cost logged per call** | `api/app/llm/` |

### Rules for this table

- This table must be **reproduced in `README.md`** with real file paths once the code exists.
  The brief explicitly requires a concept → location mapping.
- **Fetching a posting URL is NOT a counted swap.** It is incidental implementation. Never list
  "web scraping pipeline" among the five concepts — that would spend a swap we do not need.
- Because we use zero swaps, there are **no swap justifications** to write. Keep it that way.

---

## 5. Architecture

```
┌──────────────────────┐
│  Next.js frontend    │  :3000
│  (App Router, TS)    │
└──────────┬───────────┘
           │ HTTP + JWT (Authorization: Bearer)
           ▼
┌──────────────────────┐        ┌────────────────────────┐
│  FastAPI             │ :8000  │  Supabase Postgres     │
│  - validation        │───────►│  (hosted, free tier)   │
│  - auth              │        └────────────────────────┘
│  - enqueue only      │
└──────────┬───────────┘
           │ enqueue
           ▼
┌──────────────────────┐        ┌────────────────────────┐
│  Redis               │◄──────►│  RQ worker             │
│  - queue             │        │  - fetch/clean text    │
│  - cache             │        │  - Groq extract+score  │
└──────────┬───────────┘        │  - validate, persist   │
           │                    │  - write cost row      │
           ▼                    └────────────────────────┘
┌──────────────────────┐
│  rq-scheduler        │  weekly → build digest → PDF → email
└──────────────────────┘
```

### The rule that matters most

**The request path never waits on the network or the model.**

`POST /jobs` returns `202 Accepted` with a job id and `status: "pending"`. The client polls
`GET /jobs/{id}` until `status` becomes `"scored"` or `"failed"`. This is what makes the
background-job concept *load-bearing* rather than decorative — and that is the difference between
a strong capstone and a checkbox one.

Never call Groq inside a request handler. Never render a PDF inside a request handler except on
the explicit on-demand `/reports/weekly.pdf` route, and even there, reuse cached digest data.

---

## 6. Repository layout

```
jobfit/
├── CLAUDE.md                   # this file
├── README.md                   # the graded front page — see section 14
├── docker-compose.yml
├── .env.example                # every var, no real values
├── .gitignore
├── docs/
│   └── My 10x Solution - {Your Name and Surname}.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── migrations/
│   ├── seed.py                 # demo data — must work standalone
│   └── app/
│       ├── main.py             # FastAPI app, CORS, router registration
│       ├── config.py           # pydantic-settings; ALL env access goes here
│       ├── db.py               # engine, session dependency
│       ├── models/             # SQLAlchemy models
│       ├── schemas/            # Pydantic request/response models
│       ├── routers/
│       │   ├── auth.py
│       │   ├── profile.py
│       │   ├── jobs.py
│       │   ├── applications.py
│       │   ├── reports.py
│       │   └── usage.py
│       ├── auth/               # JWT create/verify, password hashing, deps
│       ├── workers/
│       │   ├── queue.py        # RQ queue + connection
│       │   ├── tasks.py        # score_job()
│       │   └── scheduler.py    # weekly digest registration
│       ├── llm/
│       │   ├── base.py         # LLMProvider interface
│       │   ├── groq_provider.py
│       │   ├── fallback.py     # deterministic keyword scorer
│       │   └── prompts.py
│       ├── cache/
│       ├── ingest/             # text cleaning, URL fetching
│       ├── reports/
│       │   ├── builder.py      # digest data assembly
│       │   ├── pdf.py          # WeasyPrint render
│       │   ├── email.py
│       │   └── templates/digest.html
│       └── tests/
└── web/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── app/                # App Router
        ├── components/
        └── lib/api.ts          # single typed API client
```

If this repo contains other coursework, the capstone must live in its own clearly named folder.

---

## 7. Tech stack — decided, do not re-litigate

| Layer | Choice | Notes |
|---|---|---|
| Backend language | Python 3.11+ | |
| Framework | **FastAPI** + Uvicorn | Pydantic validation delivers concept 1 nearly free; `/docs` makes the repo look finished |
| Database | **Supabase Postgres** (free tier) | Hosted. Not a container. See section 8 |
| ORM / migrations | SQLAlchemy 2.x + Alembic | Migrations in the repo are part of proving concept 2 |
| Auth | `python-jose[cryptography]` + `passlib[bcrypt]` | JWT access tokens, bcrypt hashes. Never roll your own hashing |
| Queue + scheduler | **RQ + rq-scheduler + Redis** | Redis runs as a container |
| Cache | **Redis** (same instance, separate key prefix) | `cache:` prefix, TTL on every key |
| LLM | **Groq** (Llama 3.x), OpenAI-compatible API | Behind an `LLMProvider` interface. Verify the current model ID at setup |
| HTTP client | `httpx` | Explicit timeouts everywhere |
| HTML → text | `trafilatura` | Good at pulling readable content out of a job page |
| PDF | **WeasyPrint** | Jinja2 HTML + CSS → PDF. Needs system deps — hence Docker |
| Email | **Mailtrap** test mode (default) or **Resend** free tier | Test mode is explicitly blessed by the brief |
| Config | `pydantic-settings` | |
| Tests | `pytest` + `httpx.AsyncClient` | |
| Frontend | **Next.js (App Router, TypeScript, Tailwind)** | Its own container |
| Orchestration | **Docker Compose** | `docker compose up` starts everything |

**Verify before building (M1):** that Groq, Supabase, and the email provider all allow signup
without a credit card. Free tiers change. If one now demands a card, swap it and note the swap in
`README.md`. Do this on day one, not in week three.

---

## 8. Supabase — read this before wiring the DB

Supabase is **hosted**, so Postgres is **not** a service in `docker-compose.yml`. The API and
worker containers connect out to Supabase over the network.

Consequences and gotchas:

- **Two connection strings.** Supabase exposes a direct connection (port `5432`) and a pooler
  (port `6543`). Long-lived app connections generally want the pooler; **Alembic migrations want
  the direct connection**, because transaction-mode pooling does not play well with prepared
  statements and DDL. Keep both in env: `DATABASE_URL` and `DIRECT_URL`. Verify current port
  conventions in the Supabase dashboard — they have changed before.
- **Use the connection string, not the Supabase client SDK.** We are building a normal SQLAlchemy
  app. Treat Supabase purely as managed Postgres. Do not pull in `supabase-py`.
- **Do not use Supabase Auth.** Concept 3 requires *we* implement authentication. Our own JWT +
  bcrypt implementation is the graded artifact. Supabase Auth would hand that concept away.
- **Do not rely on Row Level Security for authorization.** Ownership checks happen in our code, on
  every query, so they are visible and reviewable. RLS may be enabled as defence in depth, but it
  is never the only check.
- **Free tier projects pause when idle.** The first request after a pause is slow or fails. Warm
  the project before any demo, and mention this in the README's demo path.
- Use `sslmode=require`.
- For fully offline development, a local Postgres container is an acceptable fallback — but the
  committed default configuration targets Supabase.

---

## 9. Data model

```sql
users(id, email UNIQUE, password_hash, created_at)

profiles(id, user_id FK, cv_text, skills[], years_experience,
         target_roles[], locations[], updated_at)

jobs(id, user_id FK, source_url NULLABLE, content_hash, raw_text,
     title, company, seniority, required_skills[], min_years,
     location, remote, fit_score, rationale[], blockers[],
     status, created_at, scored_at)
     -- UNIQUE (user_id, content_hash)

applications(id, job_id FK, state, applied_at, last_touch_at, notes)

llm_calls(id, user_id FK, job_id FK NULLABLE, model, prompt_tokens,
          completion_tokens, est_cost_usd, latency_ms, success,
          error_kind NULLABLE, created_at)
```

- `jobs.status` ∈ `pending | fetching | scoring | scored | extraction_failed | fetch_failed`
- `applications.state` ∈ `saved | applied | interviewing | offer | rejected | ghosted`
- **`llm_calls` is not optional.** The brief's concept 7 says *"with validation and a cost log."*
  This table **is** the cost log. Every call writes a row — success or failure — and `GET /usage`
  exposes the summary.
- Transitions between `applications.state` values are validated against an explicit allowed-
  transition map in code. An invalid transition returns `409`.

---

## 10. API contract

All routes except `/auth/*` and `/healthz` require `Authorization: Bearer <jwt>`.

| Method | Path | Behaviour |
|---|---|---|
| `POST` | `/auth/register` | `201`; `409` if email taken |
| `POST` | `/auth/login` | `200` + JWT; `401` on bad credentials |
| `GET` | `/auth/me` | Current user |
| `PUT` | `/profile` | Upsert CV text and target criteria |
| `GET` | `/profile` | |
| `POST` | `/jobs` | Body `{text}` or `{url}`. `202` + job id + `status: pending`. `409` if `content_hash` already exists for this user |
| `GET` | `/jobs` | Filters: `min_score`, `state`, `company`, `status`. Paginated (`limit`, `offset`) |
| `GET` | `/jobs/{id}` | `200`, or `404` if not owned — **do not leak existence with 403** |
| `DELETE` | `/jobs/{id}` | `204` |
| `POST` | `/jobs/{id}/rescore` | Re-enqueue, bypassing cache. `202` |
| `PATCH` | `/applications/{id}` | State transition; `409` on invalid transition |
| `GET` | `/reports/weekly.pdf` | `200`, `Content-Type: application/pdf` |
| `POST` | `/reports/send` | Trigger digest email now (demo convenience). `202` |
| `GET` | `/usage` | LLM cost log summary: calls, tokens, est. spend, cache hit rate |
| `GET` | `/healthz` | Unprotected liveness |

### Non-negotiable API rules

- Validation errors surface as `422` with Pydantic's detail body. Do not flatten them to `400`.
- Every list endpoint is paginated. No unbounded queries.
- `404`, never `403`, for rows owned by another user.
- CORS allows only the frontend origin, from config. Never `allow_origins=["*"]` with credentials.

---

## 11. The LLM job — narrow and validated

**One prompt, one output shape.** The model receives cleaned posting text plus a profile summary,
and must return only:

```json
{
  "title": "string",
  "company": "string",
  "seniority": "junior|mid|senior|lead|unknown",
  "required_skills": ["string"],
  "min_years": 0,
  "location": "string",
  "remote": "onsite|hybrid|remote|unknown",
  "fit_score": 0,
  "rationale": ["string", "string", "string"],
  "blockers": ["string"]
}
```

### Validation rules — these make the concept defensible

1. Parse into a Pydantic model. A parse failure is a **first-class outcome**, not an exception that
   kills the worker.
2. **One** repair retry with a corrective instruction. On second failure: set
   `status = extraction_failed`, store the raw response for inspection, stop. No infinite retries.
3. **Clamp `fit_score` to 0–100 server-side.** Never trust the model's arithmetic.
4. Truncate posting text to a token ceiling before sending; record the ceiling in the cost log.
5. `rationale` is capped at 3 items; `blockers` at 5.
6. Every call writes an `llm_calls` row — **including failures**, with `error_kind` set.
7. Request JSON output mode where the provider supports it, but still validate. Provider-side JSON
   mode is a hint, not a guarantee.

### Fallback path — build this, it saves the demo

`llm/fallback.py` implements a deterministic keyword-overlap scorer between `profiles.skills` and
extracted/literal skill tokens. If Groq is down, rate-limited, or unconfigured, the system still
produces a number and marks the row `scored_by: "fallback"`. The demo must never depend on a free
tier being healthy at that exact moment.

### Cost logging

Groq's free tier costs nothing, but the brief asks for a cost log. Record token counts and compute
`est_cost_usd` from a per-model rate constant in `config.py` (may be `0.0`). The discipline of
measuring is the graded part.

---

## 12. Frontend — Next.js

Deliberately small. The brief says: **no pixel-perfect UI, no mobile app.** A clean, functional
interface is the target — good enough to demo and screenshot, not a design exercise.

### Pages

| Route | Contents |
|---|---|
| `/login` | Login + register, tabbed |
| `/` (dashboard) | Job list: score badge, title, company, state chip. Filter by min score and state. Sort by score |
| `/jobs/new` | Big textarea for pasted posting + optional URL field. Submits, then **polls** `GET /jobs/{id}` until scored, showing a pending state |
| `/jobs/[id]` | Full detail: score, rationale bullets, blockers, extracted requirements, application state control |
| `/profile` | CV textarea, skills, years, target roles, locations |
| `/usage` | Cost log table + cache hit rate. This page makes concepts 6 and 7 *visible* to a reviewer — do not skip it |

### Frontend rules

- **One API client**, `src/lib/api.ts`. No `fetch` calls scattered in components.
- Token in `localStorage`, attached as `Authorization: Bearer`. This is the pragmatic choice for a
  single-user capstone; note the XSS trade-off in the README rather than pretending it is ideal.
  Do not attempt cross-origin httpOnly cookies — it burns a day on CORS and SameSite.
- The pending → scored transition must be **visible**. Poll every 2s, cap at ~60s, then show a
  timeout state. This is where a reviewer *sees* the background-job concept working.
- Tailwind only. No component library. No animation library.
- Every network state handled: loading, empty, error. An empty dashboard says what to do next.
- Server Components for static shells; Client Components for anything with auth state or polling.

---

## 13. Docker and commands

### Services in `docker-compose.yml`

| Service | Purpose |
|---|---|
| `redis` | Queue + cache. Only stateful container |
| `api` | FastAPI on `:8000` |
| `worker` | `rq worker` — same image as `api`, different command |
| `scheduler` | `rq-scheduler` — same image, different command |
| `web` | Next.js on `:3000` |

**No `db` service** — Postgres is Supabase (section 8).

`api`, `worker`, and `scheduler` share one image. Build it once, override `command`. WeasyPrint's
system dependencies (Pango, Cairo, and friends) are installed in that image — this is precisely
why the project is containerized rather than run bare on Windows.

### The graded requirement

> *"The system starts with one or two documented commands on a clean machine."*

Target exactly this, and test it on a fresh clone:

```bash
cp .env.example .env     # fill in 4 values
docker compose up --build
docker compose exec api python seed.py
```

Two commands after configuration. If it takes more, fix the setup, not the README.

### Other commands

```bash
docker compose exec api alembic upgrade head          # migrations
docker compose exec api alembic revision --autogenerate -m "msg"
docker compose exec api pytest
docker compose logs -f worker                         # watch scoring happen
```

---

## 14. Environment variables

Every one of these lives in `.env.example` with placeholder values. **Never commit `.env`.**

```
# Database (Supabase)
DATABASE_URL=postgresql+psycopg://...:6543/postgres?sslmode=require
DIRECT_URL=postgresql+psycopg://...:5432/postgres?sslmode=require

# Auth
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Redis
REDIS_URL=redis://redis:6379/0

# LLM
GROQ_API_KEY=
GROQ_MODEL=
LLM_MAX_INPUT_TOKENS=6000

# Email
EMAIL_PROVIDER=mailtrap
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=
DIGEST_FROM=
DIGEST_TO=

# App
FRONTEND_ORIGIN=http://localhost:3000
CACHE_TTL_SECONDS=604800
DIGEST_CRON=0 8 * * MON
```

All env access goes through `config.py`. No `os.getenv` anywhere else in the codebase.

`.gitignore` must cover: `.env`, `.env.*` (except `.env.example`), `__pycache__/`, `*.pyc`,
`node_modules/`, `.next/`, `*.db`, `*.sqlite`, and generated PDFs.

---

## 15. Build order — follow strictly

The brief's rule: **finish one milestone before starting the next**, and inside M3,
**never have two half-built concepts open at once.**

> **Section 21 breaks these milestones into 24 numbered commits.** That is the operational plan —
> work through it in order, one commit at a time, pushing after each.

| Milestone | Timebox | Done when |
|---|---|---|
| **M1** One-pager | One evening | `docs/My 10x Solution - {Name}.md` exists with problem, audience, 10x claim, 7 concepts, non-goal. **Groq, Supabase, and email accounts verified card-free.** |
| **M2** Walking skeleton | One weekend | `POST /jobs` with pasted text → row in Supabase → `GET /jobs/{id}` returns it. No auth, no LLM, no styling. Ugly is fine. It runs. |
| **M3** Concepts, one at a time | ~2 weeks | Each concept runs and is committed before the next starts |
| **M4** Runnable by a stranger | One weekend | README with exact commands, `seed.py`, written 5-minute demo path. Someone else clones and runs it from the README alone. |
| **M5** Package and submit | One evening | Requirements checklist walked, every box ticked, repo public |

### M3 ordering — this sequence is not arbitrary

1. **Auth** — first, because retrofitting ownership checks onto existing rows is miserable.
2. **Redis + RQ worker** — with a trivial task, proving the async round-trip end to end.
3. **Groq extraction + cost log** — *after* the worker exists, so the first model call already runs
   off the request path and never has to be moved later.
4. **Caching** — once there is something expensive worth caching.
5. **PDF digest** — render to a file first, email second.
6. **rq-scheduler cron** — last; scheduling a function that already works is trivial.
7. **Next.js frontend** — can be built incrementally alongside, but never at the cost of an
   unfinished backend concept.

---

## 16. Coding conventions

- **Type hints everywhere** in Python. `mypy`-clean is nice, not required.
- **Routers stay thin.** Validate, authorize, delegate, return. Business logic lives in services or
  workers, never in a route handler.
- Pydantic schemas are separate from SQLAlchemy models. Never return an ORM object directly.
- Explicit timeouts on every `httpx` call. No unbounded network waits.
- Structured logging with `job_id` and `user_id`. **Never log CV text, tokens, or API keys.**
- Small commits, one concept per commit, messages that name the concept
  (`feat(cache): redis-backed extraction cache`).
- No premature abstraction. Two implementations before an interface — the one exception is
  `LLMProvider`, which is abstracted from the start because provider swapping is a live risk.
- Tests focus on the scary cases: malformed LLM JSON, duplicate ingest, invalid state transitions,
  expired JWT, cross-user access attempts.

---

## 17. README requirements — this file is graded

`README.md` must contain, at minimum:

1. What this is and the problem it solves — one paragraph a stranger understands.
2. The **10x claim**.
3. The **concept → file-location table** from section 4, with real paths.
4. Exact setup and run commands (section 13), verified on a clean clone.
5. A **5-minute demo path**, written literally: open X → click Y → see Z.
6. The **non-goal**, stated.
7. A **Future ideas** section — where scope creep goes to be parked.
8. Architecture diagram (ASCII is fine).

### Submission checklist

- [ ] `docs/My 10x Solution - {Your Name and Surname}.md` — **exact filename**, `.md` or `.docx`
- [ ] 5+ concepts implemented and listed in README with locations
- [ ] Zero swaps — nothing to justify
- [ ] Starts with one or two documented commands on a clean machine
- [ ] `seed.py` works; the README demo path works
- [ ] No secrets in the repo; `.gitignore` verified
- [ ] Repo is **public** on GitHub
- [ ] Submit the **repo link** on the portal — never a ZIP upload

**No live presentation.** The repository and the document do the talking.

### Stretch, only after everything above is ticked

- Deploy to a free hosting tier, live URL in the README
- 2-minute demo GIF or video linked in the README
- Measure the 10x with one real before/after number
- Expand the test suite

---

## 18. Risk register

| Risk | Mitigation |
|---|---|
| Groq starts demanding a card | Verified in M1. `LLMProvider` interface makes swapping a one-file change. Fallback scorer always works |
| Supabase free project pauses when idle | Warm it before demos; note it in the README |
| Job boards block URL fetching | **Paste-text is the primary path.** URL fetch is convenience only. Respect `robots.txt`, set a real User-Agent, rate-limit ourselves |
| WeasyPrint system deps eat a day | Solved by Docker. Do not attempt bare-metal Windows |
| Email deliverability on free tiers | Mailtrap test mode + a screenshot in the README |
| Scope creep | Non-goal written down; Future ideas section absorbs new ideas |
| Two half-built concepts open at once | One open task at a time — the brief's own rule |
| Alembic fails through the pooler | Use `DIRECT_URL` for migrations (section 8) |

---

## 19. Demo data rules

`seed.py` creates one demo user, one profile built from the author's **own** CV, and 8–12 job
postings with varied scores — a couple of strong matches, some mid, a couple with clear blockers.

Postings must be **self-written or from public sources**. No real applicant data, no third-party
résumés. The brief's "no other people's personal data" rule is not negotiable.

Seed the scored results directly where sensible, so a reviewer sees a populated dashboard without
waiting on a live model, then have them ingest one fresh posting to watch the pipeline run.

---

## 20. When in doubt

1. Does this serve one of the 5 frozen features? If no → Future ideas.
2. Does it break a hard constraint in section 2? If yes → do not do it.
3. Does it make a concept in section 4 more visible to a reviewer? If yes → it is probably worth it.
4. Can it be shipped smaller? Then ship it smaller.

A small solution that runs beats a big solution that does not.

---

## 21. Commit plan — 24 commits in 5 stages

The operational version of section 15. **Work through these in order.** One commit at a time,
pushed to GitHub after each. Never start commit N+1 while N is half-built.

**Every commit must satisfy three rules:**

1. **It runs.** The stack starts and `/healthz` answers. A commit that breaks `docker compose up`
   does not get pushed.
2. **It is one thing.** One concept, one feature, one fix. If the diff needs the word "and" to
   describe it, split it.
3. **It is verifiable in under two minutes.** Each commit below has a *Verify* line. Run it before
   committing. If you cannot verify it, it is not done.

A note on ordering: it is tempting to build the frontend first because it is the visible part. Do
not. The frontend consumes an API that must already exist and be stable — building it early means
rewriting it twice. The UI lands in Stage 4, and Stage 4 is fast precisely because Stages 1–3 are
finished.

Branch strategy: `main` only. A solo three-week capstone does not need feature branches, and a
clean linear history reads better to a reviewer than a tangle of merges.

---

### Stage 0 — Foundation (2 commits) · one evening

**C1 · `chore: scaffold repo, gitignore, env template`**
Directory skeleton from section 6. `.gitignore` covering `.env`, `__pycache__/`, `node_modules/`,
`.next/`, `*.db`, generated PDFs. `.env.example` with every variable from section 14, placeholder
values only. `README.md` stub with the problem statement and 10x claim. `CLAUDE.md` committed.
*Verify:* `git status` is clean after creating a real `.env` — it must not appear.
*Why first:* the gitignore has to exist before any secret can accidentally be staged.

**C2 · `chore(docker): compose with redis and api container`**
`docker-compose.yml` with `redis` and `api`. `api/Dockerfile` including WeasyPrint system deps.
FastAPI app with `/healthz` only. `config.py` using `pydantic-settings`.
*Verify:* `docker compose up --build`, then `curl localhost:8000/healthz` returns 200.

---

### Stage 1 — Walking skeleton, M2 (2 commits) · one weekend

**C3 · `feat(db): supabase connection, alembic, jobs table`** — *concept 2*
SQLAlchemy engine against Supabase, session dependency, Alembic initialised with `DIRECT_URL`,
first migration creating `jobs`.
*Verify:* `alembic upgrade head` succeeds; the table is visible in the Supabase dashboard.

**C4 · `feat(api): ingest pasted posting, read it back`** — *concept 1*
`POST /jobs` accepting `{text}` and `GET /jobs/{id}`. Pydantic schemas. `content_hash` computed.
Status `pending`. No auth, no LLM, no styling — **ugly is correct here.**
*Verify:* POST a posting, GET it back, restart the containers, GET it again. It survives.

> **This is the walking skeleton.** One request touches every layer and returns. Everything after
> this adds muscle to a skeleton that already walks. You never rewrite it.

---

### Stage 2 — Backend concepts, M3 (13 commits) · ~2 weeks

**C5 · `feat(auth): register, login, jwt issuance`** — *concept 3*
`users` table and migration, bcrypt via passlib, JWT via python-jose, `/auth/register`,
`/auth/login`, `/auth/me`.
*Verify:* register → login → call `/auth/me` with the token. Wrong password returns 401.

**C6 · `feat(auth): protect job routes, enforce ownership`**
`get_current_user` dependency on all job routes. `user_id` FK on `jobs` (migration). Every query
filtered by owner. **404, not 403, for other users' rows.**
*Verify:* create two users; user B requesting user A's job gets 404, not 403.

**C7 · `feat(profile): cv profile crud`**
`profiles` table, `GET`/`PUT /profile`. Skills, years, target roles, locations.
*Verify:* upsert a profile twice — the second call updates rather than duplicating.

**C8 · `feat(queue): rq worker with trivial task`** — *concept 4, part 1*
`worker` service sharing the api image. RQ queue wiring. `POST /jobs` now returns **202** and
enqueues a no-op that flips status `pending → scored` after a sleep.
*Verify:* POST a job, watch `docker compose logs -f worker`, poll until status changes.

> Prove the async round-trip **before** adding the model. This ordering means your first Groq call
> already runs off the request path and never has to be moved.

**C9 · `feat(llm): groq provider with strict schema validation`** — *concept 7, part 1*
`LLMProvider` interface, Groq implementation, prompt from section 11, Pydantic validation of the
response, `fit_score` clamped 0–100 server-side, input truncated to the token ceiling.
*Verify:* score a real posting; the extracted JSON validates and lands in the row.

**C10 · `feat(llm): repair retry, failure states, cost log`** — *concept 7, part 2*
One corrective retry on parse failure, then `status = extraction_failed` with the raw response
stored. `llm_calls` table and migration. Every call writes a row, **including failures**.
`GET /usage` returns the summary.
*Verify:* point the provider at a deliberately broken prompt; the worker survives, the row is
marked failed, and `/usage` shows the failed call.

**C11 · `feat(llm): deterministic fallback scorer`**
Keyword-overlap scorer in `llm/fallback.py`. Used when Groq is unconfigured, down, or
rate-limited. Rows carry `scored_by: groq | fallback`.
*Verify:* unset `GROQ_API_KEY`, ingest a posting — it still scores, marked `fallback`.

> This commit is what stops a rate limit from destroying your demo on submission day.

**C12 · `feat(cache): redis extraction cache`** — *concept 6*
Cache extraction results by `content_hash` under a `cache:` prefix with TTL. A cache hit skips the
Groq call entirely. Hit/miss counters exposed via `/usage`.
*Verify:* ingest the same posting twice. The second is near-instant and adds **no** new
`llm_calls` row. `/usage` shows the hit.

**C13 · `feat(jobs): filtering, pagination, rescore, delete`**
`GET /jobs` with `min_score`, `state`, `company`, `status`, plus `limit`/`offset`.
`POST /jobs/{id}/rescore` bypassing cache. `DELETE /jobs/{id}`.
*Verify:* filters narrow correctly; no endpoint can return an unbounded list.

**C14 · `feat(applications): state machine with validated transitions`**
`applications` table, `PATCH /applications/{id}`, explicit allowed-transition map, 409 on an
illegal move, `last_touch_at` maintained.
*Verify:* `saved → applied` succeeds; `rejected → saved` returns 409.

**C15 · `feat(reports): weekly digest rendered to pdf`** — *concept 5, part 1*
`reports/builder.py` assembling digest data (new high scores, stale applications), Jinja2 template,
WeasyPrint render, `GET /reports/weekly.pdf`.
*Verify:* download the PDF and open it. It has real seeded content, not lorem ipsum.

**C16 · `feat(reports): email delivery via smtp`** — *concept 5, part 2*
SMTP sender, Mailtrap test mode by default, PDF attached, `POST /reports/send` to trigger now.
*Verify:* trigger it; the email with attachment appears in the Mailtrap inbox.

**C17 · `feat(scheduler): weekly cron for the digest`** — *concept 4, part 2*
`scheduler` service running rq-scheduler, weekly job registered from `DIGEST_CRON`.
*Verify:* temporarily set the cron to every minute, watch it fire, then set it back.

> **All 7 concepts are now implemented.** Update the README concept table in this commit — do not
> leave it for the end, when you will be tired and will guess at paths.

---

### Stage 3 — Frontend (4 commits) · one weekend

**C18 · `feat(web): next.js scaffold, api client, login`**
`web` service in compose. App Router, TypeScript, Tailwind. Single typed client at `lib/api.ts` —
**no scattered `fetch` calls.** Token in localStorage, attached as a Bearer header. `/login` with
register and login tabs. CORS configured on the API for `FRONTEND_ORIGIN`.
*Verify:* register and log in from the browser; refreshing keeps you logged in.

**C19 · `feat(web): dashboard and job detail`**
`/` job list with score badges, company, state chips, filters, sort by score. `/jobs/[id]` with
rationale bullets, blockers, extracted requirements, and the application-state control.
*Verify:* seeded jobs render; filters work; the state control persists a change.

**C20 · `feat(web): ingest page with live polling`**
`/jobs/new` — textarea plus optional URL. On submit, poll `GET /jobs/{id}` every 2s, capped at
60s, with visible pending → scored → timeout states.
*Verify:* paste a posting and watch it go pending → scored without a manual refresh.

> This screen is where a reviewer **sees** the background-job concept working. Do not rush it.

**C21 · `feat(web): profile and usage pages`**
`/profile` CV editor. `/usage` showing the cost log table, token totals, and cache hit rate.
*Verify:* `/usage` numbers move after ingesting a fresh posting, and again on a repeat (cache hit).

> Caching and cost logging are otherwise invisible. This page makes two graded concepts legible in
> ten seconds. It is the highest-value page in the app per line of code.

---

### Stage 4 — Ship it, M4 + M5 (3 commits) · one weekend + one evening

**C22 · `feat(seed): demo data script`**
`seed.py` creating one demo user, a profile from **your own** CV, and 8–12 self-written or public
postings with varied outcomes — strong matches, mid, and some with clear blockers. Pre-scored
where sensible so the dashboard is populated instantly.
*Verify:* on a wiped database, `seed.py` produces a dashboard worth looking at.

**C23 · `test: cover the scary cases`**
pytest with `httpx.AsyncClient`: malformed LLM JSON, duplicate ingest (409), illegal state
transition (409), expired JWT (401), cross-user access (404), cache hit adds no `llm_calls` row.
*Verify:* `docker compose exec api pytest` passes from clean, deterministically.

**C24 · `docs: readme, demo path, overview document`**
README per section 17: concept → location table with **real** paths, exact run commands, the
written 5-minute demo path, the non-goal, Future ideas, architecture diagram.
`docs/My 10x Solution - {Your Name and Surname}.md` — **exact filename.**
*Verify:* clone the repo into a fresh directory and run it from the README alone, touching nothing
else. If you reach for knowledge that is not in the README, the README is not finished.

---

### After C24 — stretch, in this order

| | Commit | Value |
|---|---|---|
| C25 | `chore: deploy to free hosting tier` | A live URL in a portfolio hits differently |
| C26 | `docs: demo gif in readme` | Does the presenting for you — there is no live session |
| C27 | `docs: measured 10x number` | Turns the claim into evidence |

---

### Commit hygiene

- Use conventional prefixes: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.
- **Scope names the concept** — `feat(cache):`, `feat(llm):`, `feat(auth):`. A reviewer skimming
  `git log` should be able to see all seven concepts land. This is free credibility.
- Push after every commit. A capstone with 24 commits spread across three weeks reads like real
  work; one commit reading "final project" reads like a panic.
- Never commit `.env`, real API keys, a database file, `node_modules/`, `.next/`, or generated PDFs.
- If you catch a secret already committed: **rotate the key immediately.** Removing it from
  history does not un-leak it.
