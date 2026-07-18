# Tutorial 1 — Building an open-source AI-assisted rostering system for NSW Health nurses

**What you'll build:** a web app where a nurse unit manager (NUM) enters their staff, ward requirements, and leave requests, clicks "Generate", and gets back a fortnightly roster that satisfies NSW award rules — plus an AI assistant that lets staff make requests in plain English ("I can't do nights the week of the 14th") and explains *why* the roster came out the way it did.

**The single most important thing to understand before you start:**
Generating a valid roster is not a machine-learning problem — it is a *constraint optimisation* problem, known in the literature as the **Nurse Scheduling Problem (NSP)**. The "AI" that actually builds the roster is a constraint solver (we'll use Google OR-Tools' CP-SAT solver). The *LLM* part (Claude/GPT) sits on top as an assistant: translating natural-language requests into constraints, explaining rosters, and suggesting swaps. Structuring the project this way is what makes it credible — LLMs alone cannot reliably produce award-compliant rosters.

**Time estimate:** this is a semester-sized project. Budget roughly 8–12 weeks part-time.

**Prerequisite skills** (with where to learn each — do these *as you hit them*, not all up front):

| Skill | Best resource |
|---|---|
| Python (intermediate) | You likely have this from your degree |
| Git & GitHub | Search YouTube: *"Git and GitHub for Beginners freeCodeCamp"* (their full course is excellent) |
| FastAPI (Python web framework) | Official tutorial: https://fastapi.tiangolo.com/tutorial/ — genuinely one of the best-written docs in software. YouTube alternative: search *"Python API Development FastAPI freeCodeCamp"* (Sanjeev Thiyagarajan's 19-hour course) |
| Constraint programming / OR-Tools | Google's official guide, which includes a **nurse scheduling example you will build on directly**: https://developers.google.com/optimization/scheduling/employee_scheduling |
| SQL / PostgreSQL | Search YouTube: *"PostgreSQL tutorial freeCodeCamp"* |
| React | Official docs: https://react.dev/learn — or search YouTube: *"React course 2025 freeCodeCamp"* |
| Docker (later, for deployment) | Search YouTube: *"Docker tutorial for beginners TechWorld with Nana"* |

> Tip on YouTube links: video URLs rot and get re-uploaded, so I've given you durable official links where they're genuinely the best resource, and *search phrases* for YouTube where a video course is better. The channels named (freeCodeCamp, TechWorld with Nana) are large, stable, and consistently good.

---

## Step 1 — Research the domain and write `CONSTRAINTS.md` (week 1)

Do this **before writing any code**. Your solver is only as good as your understanding of the rules. Create `docs/CONSTRAINTS.md` in this repo and document, with citations:

1. **The award rules.** Read the *NSW Nurses and Midwives' (State) Award* (search "NSW Nurses and Midwives State Award" on the NSW Industrial Relations Commission site, or get the NSWNMA's summary). Extract every rosterable rule, e.g.:
   - Full-time = 38 hrs/week, commonly rostered as 76 hrs/fortnight with an ADO (allocated day off) each 4-week cycle.
   - Minimum break between rostered shifts (the award specifies this — verify the current figure, historically 8 hours with provisions around 10; **check the current award text, don't trust this doc**).
   - Maximum consecutive shifts before a day off.
   - Weekend/night penalty implications (matters for *fairness*, not just legality — everyone wants their fair share of penalty shifts, and nobody wants all of them).
   - Rules around rotating rosters and notice periods for roster changes.
2. **NSW Health rostering guidelines.** NSW Health publishes rostering best-practice resources: https://www.health.nsw.gov.au/Rostering/Pages/healthroster.aspx and https://www.health.nsw.gov.au/Performance/rostering/Pages/resources.aspx
3. **Staffing requirements.** NSW is rolling out **Safe Staffing Levels** (nurse-to-patient ratios, e.g. 1:3 in EDs) alongside the older NHPPD (Nursing Hours Per Patient Day) model. Your ward model needs: shifts per day (typically AM / PM / Night), minimum staff per shift, and minimum *skill mix* per shift (e.g. at least one RN in-charge-capable; ratios of RNs to ENs to AINs).
4. **Talk to a nurse if you possibly can.** Ten minutes with a NUM or a ward nurse about what makes rosters *actually* good or bad (self-requests honoured, night-shift clusters, no "late-then-early" pairs) will teach you things no document will. These become your *soft constraints*.

Classify every rule as:
- **Hard constraint** — the roster is invalid if violated (award minimum breaks, min staffing).
- **Soft constraint** — violating it is allowed but penalised (unfulfilled requests, unfair weekend distribution, split days off).

This hard/soft classification maps directly onto how CP-SAT works, so this document *is* your solver spec.

---

## Step 2 — Set up the repo like a real open-source project (half a day)

1. Create the GitHub repo. Add:
   - **LICENSE** — MIT (maximally permissive) or AGPL-3.0 (forces anyone who runs a modified version as a service to share their changes — a deliberate choice for health software; read https://choosealicense.com to decide).
   - **README.md** with the project vision, a screenshot placeholder, and a "not affiliated with NSW Health" disclaimer.
   - **CONTRIBUTING.md**, **CODE_OF_CONDUCT.md** (GitHub has templates for both under *Insights → Community Standards*).
2. Structure:
   ```
   roster-engine/
   ├── backend/
   │   ├── app/
   │   │   ├── main.py          # FastAPI entrypoint
   │   │   ├── models.py        # SQLAlchemy models
   │   │   ├── schemas.py       # Pydantic schemas
   │   │   ├── solver/          # OR-Tools roster generation
   │   │   ├── ai/              # LLM assistant layer
   │   │   └── routers/         # API endpoints
   │   ├── tests/
   │   └── pyproject.toml
   └── frontend/                # React app (created later with Vite)
   ```
3. Set up Python tooling: `uv` or `poetry` for dependencies, `ruff` for linting, `pytest` for tests.
4. Add a GitHub Actions workflow that runs lint + tests on every push (search GitHub docs for "building and testing Python" — it's a 20-line YAML file).

---

## Step 3 — Design the data model (week 1–2)

Model the domain in PostgreSQL via SQLAlchemy. Core tables:

- **Staff** — name, employment fraction (FTE), classification (RN / EN / AIN / CNS / NUM), skills/certifications (e.g. triage, in-charge), contracted hours per fortnight.
- **Ward** — name, shift structure (e.g. AM 07:00–15:30, PM 13:00–21:30, Night 21:00–07:30).
- **DemandTemplate** — for each ward, day-of-week and shift: minimum staff count and minimum skill mix (e.g. "AM weekday: 5 total, ≥3 RN, ≥1 in-charge").
- **Request** — staff member, date range, type (annual leave, ADO, unavailable, *prefers* AM, etc.), and whether it's approved (hard) or a preference (soft).
- **RosterPeriod** — the fortnight/month being generated, and its status (draft / published).
- **Assignment** — the output: (staff, date, shift) triples, with a flag for solver-generated vs manually edited.

Start with SQLite in dev (zero setup, SQLAlchemy makes swapping trivial), move to Postgres when you deploy.

**Real-world data entry:** the primary way staff/doctor details and shift requests get into the system is by uploading an Excel spreadsheet (a NUM's existing hiring/leave records aren't going to arrive as JSON). The CRUD endpoints in Step 5 populate the same `staff`/`request` tables, but should be treated as the fallback for one-off edits and testing, not the main input path.

**Checkpoint:** you can seed a fake ward of ~20 staff and a demand template from a script.

---

## Step 4 — Build the solver core (weeks 2–4) ⭐ the heart of the project

This is the step to spend the most time on, and the one that will teach you the most.

1. **Learn CP-SAT with Google's example.** Work through https://developers.google.com/optimization/scheduling/employee_scheduling top to bottom. Their nurse-scheduling example is ~100 lines and already handles "each shift assigned, nobody works two shifts a day, distribute shifts evenly". Run it, tweak it, break it.
2. **Understand the modelling pattern.** You create one boolean variable per (nurse, day, shift): `shifts[(n, d, s)]`. Every rule becomes a linear constraint over those booleans:
   - *Min staffing:* for each (day, shift): `sum over nurses >= demand`.
   - *One shift per day:* for each (nurse, day): `sum over shifts <= 1`.
   - *Min break / no late-then-early:* forbid the pair `shifts[(n, d, PM)] + shifts[(n, d+1, AM)] <= 1` (generalise from actual shift times).
   - *Max consecutive days:* for each window of length `max+1`, sum of "worked that day" ≤ max.
   - *Contracted hours:* per nurse per fortnight, sum of shift-hours == contracted hours (or within a tolerance band).
   - *Skill mix:* same as min staffing but summed over only the nurses holding the skill.
3. **Add soft constraints via the objective function.** For each preference, create a penalty variable; minimise the weighted sum of penalties. Weights encode policy: unfulfilled approved leave should be near-infinite (or just hard), unfulfilled "prefers AM" is cheap, unfair weekend distribution is medium. Fairness itself: minimise the *max minus min* of weekend-shift counts across staff.
4. **Wrap it in a clean interface:** a function `generate_roster(ward, staff, requests, period) -> list[Assignment] | InfeasibleReport`. When the model is infeasible (it will be, often — e.g. too much approved leave), CP-SAT can tell you nothing by default, so build a diagnostic mode: progressively relax constraint groups to report *which* rule made it impossible. NUMs will love this.
5. **Test seriously.** Property-based tests are ideal here: generate random wards, run the solver, then *independently verify* every hard constraint on the output with plain Python. This validator is also reusable as a "check my hand-edited roster" feature — arguably as valuable as generation itself.

**Academic rabbit hole (optional but great for a student):** search for "Nurse Rostering Competition INRC-II" — real benchmark instances and papers you can compare against.

**Checkpoint:** from seeded fake data you can print a valid fortnightly roster to the terminal, and your validator confirms zero hard-constraint violations.

---

## Step 5 — Expose it as an API with FastAPI (week 5)

Endpoints (all JSON, documented automatically by FastAPI's built-in Swagger UI):

- `POST /wards`, `POST /staff`, `POST /requests` — CRUD for the data model.
- `POST /staff/import` — accepts an uploaded Excel file containing staff/doctor details and shift requests, parses it into the same `staff`/`request` rows the CRUD endpoints would create. This is the main data-entry path in practice; validate rows on the way in and report which ones failed rather than rejecting the whole file on one bad row.
- `POST /roster-periods/{id}/generate` — runs the solver. Solves can take seconds-to-minutes, so run it as a background task and poll status (or just accept a 30s request in v1 — don't gold-plate).
- `GET /roster-periods/{id}` — the roster, per-staff and per-day views.
- `POST /roster-periods/{id}/validate` — run the validator on a (possibly hand-edited) roster.
- Simple auth: start with none (local tool), add per-user auth only when someone actually deploys it multi-user. Don't burn weeks on auth before the product works.

**Checkpoint:** you can drive the whole flow from the Swagger UI at `http://localhost:8000/docs` with zero frontend.

---

## Step 6 — Build the frontend (weeks 6–8)

React + Vite + TypeScript. The one hard UI problem is the **roster grid**: staff as rows, days as columns, shift codes in cells — this is how every NUM already thinks. Build:

1. Setup: `npm create vite@latest frontend -- --template react-ts`.
2. A staff/ward/requests management screen (boring CRUD forms — consider a component library like Mantine or shadcn/ui to move fast).
3. The roster grid: a table with sticky headers, colour-coded shift cells (AM/PM/ND), and click-to-edit cells. Libraries like **TanStack Table** help; for a calendar-style per-nurse view, **FullCalendar** (https://fullcalendar.io) is the standard choice.
4. A "Generate" button with progress state, and a violations panel that shows validator output inline (red cell borders on violations).
5. Hand-editing: when a NUM overrides a cell, re-run `/validate` and show what broke. *This human-in-the-loop flow is the real product* — no NUM will accept a roster they can't tweak.

**Checkpoint:** end-to-end demo: seed ward → enter a leave request → generate → see roster grid → hand-edit a cell → see the violation warning.

---

## Step 7 — Add the LLM assistant layer (weeks 8–10) — the "AI-assisted" part

Use the Claude API (https://docs.claude.com) or any LLM API. Three features, in order of value:

1. **Natural-language requests → structured constraints.** A nurse types "I can't do nights the week of March 14 and I'd prefer weekends off that fortnight". The LLM's job is *translation only*: you give it your `Request` JSON schema as a tool/structured-output definition, it emits `[{type: "unavailable", shift: "ND", start: "2026-03-14", ...}]`, and the human confirms before it's saved. The solver — not the LLM — remains the source of truth.
2. **Roster explanation.** Feed the LLM the solver's inputs, outputs, and penalty breakdown, and let it answer "why did I get three weekends this month?" ("Two staff on leave meant weekend coverage fell to the remaining eight RNs; you're at the ward median of 3"). This is pure prompting over data you already have.
3. **Swap suggestions.** "Find me someone to swap my Tuesday PM with" — here the *solver* enumerates feasible swaps (re-validate each candidate) and the LLM just presents them nicely.

Design rule worth writing in your README: **the LLM never writes to the database and never produces the roster; it proposes, humans approve, the solver decides.** For a healthcare-adjacent open-source project, that governance stance is a feature.

---

## Step 8 — Ship it (weeks 10–12)

1. **Dockerise**: one `Dockerfile` for the backend, one compose file with Postgres, frontend served as static files. Goal: a NUM-curious dev can run `docker compose up` and be inside the app in five minutes — for open source, this *is* your marketing.
2. Write real docs: quickstart, a screenshot-heavy demo walkthrough, `CONSTRAINTS.md`, and an honest "what this doesn't do" section.
3. Add a demo dataset and a `make demo` target.
4. Tag `v0.1.0`, write release notes, and post it: the NSWNMA has an active community, r/nursing and r/ausjdocs discuss rostering pain constantly, and Hacker News's "Show HN" likes constraint-solver projects.
5. **Disclaimers matter here:** state clearly it's not affiliated with NSW Health, not payroll-grade, and that award interpretation must be verified by the employer. You're a student publishing a tool, not giving industrial-relations advice.

---

## Common traps

- **Starting with the LLM instead of the solver.** An LLM-generated roster will look plausible and be quietly illegal. Solver first.
- **Modelling every award rule up front.** Get 5 hard constraints + 2 soft ones working end-to-end, then iterate. The architecture (booleans + constraints + penalties) makes adding rules cheap later.
- **Building auth/multi-tenancy early.** It's a demo/local tool until someone deploys it. Ship the solver.
- **Solver infeasibility with no explanation.** Budget real time for the diagnostic mode in Step 4.4 — it's the difference between a toy and a tool.
