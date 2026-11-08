# School-TL Telegram bot — design

## Intent / why

The user maintains a class timeline site at `reutl.vercel.app` (backed by
the separate `dotolus/School-TL` repo — a Node/Express + Firestore app)
for their child's class (`reut`/`2026-2027`/`e4`). Today, checking or
updating that timeline means opening the site's admin page. The goal of
this project is a Telegram bot that lets the user do both from a chat,
in free-form Hebrew:

- ask what's on the timeline ("מה יש השבוע?"), and
- tell the bot about something that should be added or changed, and have
  it actually update the live site.

## Goals

- A Telegram bot (Python, long-polling) that:
  - Answers free-form Hebrew questions about the class timeline, reading
    live from School-TL's `GET /api/reut/2026-2027/e4/timeline`. The
    `short` (and `full`) field carries the item's exact date within the
    month as free text (by convention, not a structured field) — Claude
    reads the actual day out of that text, so day/week-level questions
    ("יש דברים חשובים בשבוע הבא?") can be answered precisely, not just
    at month granularity.
  - Accepts free-form Hebrew requests to add a **new** timeline item,
    using the Claude API to turn the message into School-TL's item
    shape, and shows the user a Hebrew confirmation of exactly what it
    understood before writing anything.
  - On confirmation, authenticates to School-TL the same way the human
    admin page does (`POST /api/auth/login` with the shared
    `ADMIN_PASSWORD`) and calls `POST .../timeline/items` to create the
    new item.
- All natural-language understanding and Hebrew reply generation goes
  through the Claude API — no keyword/regex parsing of the user's Hebrew.
- The authorization layer is structured so that specific other Telegram
  users can be allow-listed later, each with their own permission level
  (e.g. read-only vs. read-write), without a redesign — even though v1
  only has to recognize the project owner.

## Non-goals (v1)

- **Editing or moving an existing timeline item.** The user plans a
  dedicated School-TL API for addressing a single existing entity for
  update, which doesn't exist yet. Building an edit flow against
  today's `PUT .../timeline/items/:id` (and solving match/disambiguation
  for a free-text "move the math test to December"-style request) would
  mean designing against a contract that's about to change. v1's write
  capability is therefore scoped to **creating new items** only, via the
  already-stable `POST .../timeline/items`. Edit support, and the
  disambiguation question that comes with it, is revisited once that
  new API exists.
- Actually onboarding any Telegram user besides the owner — v1 enforces
  a single hardcoded allowed Telegram user id; multi-user is a structural
  consideration, not a v1 feature.
- Any data source other than School-TL's own API. If a different
  external "public API" is meant to feed this later, that's a separate,
  future piece — nothing here assumes one exists yet.
- A webhook/serverless deployment. v1 is a single always-on
  long-polling process; no public HTTPS endpoint, no webhook secret.
- Any change to the `School-TL` repo itself (no new endpoint, no second
  credential). The bot is purely an external API client.
- Attachment upload/management on timeline items.

## Anti-goals

Either of these makes this a failure even if the bot otherwise "works":

- The bot writes to the live timeline without the user explicitly
  confirming the parsed content first. A Claude misparse must never
  reach the real site unseen.
- A secret (Telegram bot token, `ADMIN_PASSWORD`, Claude API key) ends
  up committed to the repo or written to a log in plaintext.

## Constraints (from how School-TL actually works)

- Its write endpoints recognize exactly one shared `ADMIN_PASSWORD` →
  signed session cookie. There is no per-caller credential or scoped
  permission to attach the bot to specifically.
- That session cookie is short-lived by design — a sliding
  `ADMIN_SESSION_MAX_AGE_MS` window, 4 minutes by default — so the bot
  must be able to re-login rather than assume a cached cookie is still
  valid.
- The item shape is fixed by School-TL:
  `{ type: "holiday"|"test"|"notice"|"project", m, y, title, short, full,
  detail: {...}, "required-white-shirt"?, "required-food"?,
  "required-parent-signature"? }`. Claude's extraction has to target this
  shape exactly, not an approximation of it. There is no *structured*
  day field — only month (`m`, 1-12) and year (`y`) — but by convention
  the exact date within the month is written into the `short` (and/or
  `full`) free-text field, which is where day/week-level answers have
  to come from (see Goals).
- Confirmed write contract (read from School-TL's actual
  `server/routes/timeline.routes.js` / `timelineStore.js`):
  - `POST .../timeline/items` — full item body, no `id`. → `201` + the
    created item (server-assigned `id`).
  - `PUT .../timeline/items/:id` — full item body again (validation
    requires every required field every time; this is a full replace,
    not a partial patch). → `200` + updated item, or `404` if that `id`
    doesn't exist on this dataset. **Not used by v1** (see Non-goals) —
    documented here only for context; the planned future single-entity
    update API may replace it for editing rather than reusing it.
  - `DELETE .../timeline/items/:id` → `204`, or `404`.
  - Any validation failure on `POST`/`PUT` → `400 {error: "<message>"}`.
  - `GET .../timeline` → `{ items: [...] }`, each item including its real
    `id` — so an edit always has a concrete target to reference.

## Decisions already made (in conversation, not up for re-litigation here)

- **Query source:** `GET /api/reut/2026-2027/e4/timeline` (School-TL's
  internal item shape), not the `.../events` external-contract endpoint.
- **Write auth:** reuse the existing shared `ADMIN_PASSWORD` rather than
  add a second credential to School-TL. Its API has only one
  undifferentiated admin role anyway, so a second shared secret would
  only buy independent revocability, not finer scope — and the real
  access control lives in the bot's own per-Telegram-user allow-list
  regardless.
- **NLU/NLG engine:** the Claude API, for both understanding the Hebrew
  message and composing the Hebrew reply.
- **Stack:** Python.
- **Run model:** a long-polling, always-on process (not a webhook).
- **Confirm-before-write:** required for every update, no exceptions.
- **Date handling:** exact dates live inside the `short`/`full` free
  text by convention; Claude reads them from there for day/week-level
  answers rather than relying on a structured day field that doesn't
  exist.
- **Write scope for v1:** create new items only; editing an existing
  item waits for the user's planned single-entity-update API, which
  doesn't exist yet.

## Approach

Given the decisions above, there's really one sensible shape for this,
not several competing ones:

A single Python process (e.g. `python-telegram-bot`, long-polling) that,
per incoming message:

1. **Checks the sender's Telegram user id** against an allow-list
   (config/env-driven). Anyone not on it is ignored or told they're not
   authorized. This is the extension point for multi-user + roles later
   — the list just needs more than one entry and a permission field per
   entry.
2. **Calls the Claude API once** with the user's Hebrew message and a
   tool/function schema describing two possible actions —
   `query_timeline` and `propose_new_item` (fields matching School-TL's
   item shape — no `id`, since v1 only creates) — and lets Claude's
   tool-use pick one and fill it in. This is tool-use as structured
   extraction, not a multi-step agentic loop: one call, one
   classified+extracted result. A message that reads as asking to edit
   an existing item (unsupported in v1 — see Non-goals) should be
   recognized and declined in Hebrew, not silently misfired as a new
   item or a query.
3. **If it's a query:** the bot fetches (or already fetched)
   `GET .../timeline` and asks Claude to compose a natural Hebrew answer
   from that data plus the original question — reading exact dates out
   of each item's `short`/`full` text where the question needs one (see
   Goals) — then sends it back.
4. **If it's a proposed new item:** the bot sends the user a Hebrew
   summary of exactly what it's about to create, with inline
   Yes/Cancel buttons.
   - **Yes:** log in (`POST /api/auth/login`), then
     `POST .../timeline/items`.
   - **Cancel:** nothing happens.
5. A small session wrapper around School-TL's login caches the session
   cookie and transparently re-logs-in on a `401`, matching School-TL's
   own documented sliding-session behavior.

Secrets (Telegram bot token, `ADMIN_PASSWORD`, Claude API key) live in
environment variables / a local `.env`, never committed — the same
convention School-TL's own `.env.example` already uses.

## Testing against real data

School-TL's "any school/period/class combination is addressable, no
registry" design (see its own CLAUDE.md) means integration tests can
point at a disposable, made-up dataset tag (e.g. `_test`/`0000`/`zz`)
and never touch the real `reut/2026-2027/e4` dataset during development.
Only a final, deliberate manual smoke test should run against the real
one.

## What's left to the builder

- Exact Telegram library (`python-telegram-bot` is the default
  assumption; swappable if there's a reason to prefer another).
- Exact prompt/tool-schema wording for the Claude calls.
- Exact Hebrew copy for confirmation messages and button labels.
- Config format for the Telegram user allow-list (env var list vs. a
  small JSON/YAML file) — either is fine as long as adding a second user
  with a different permission level doesn't require a code change.
- Logging/observability approach.
- Where the always-on process actually runs day to day (the user's own
  machine, a small VM, etc.) — not blocking the design.

## Context for whoever reads this later

A separate, unrelated exploration (a Django "school atmosphere survey"
platform, built in a git worktree against a different sibling repo,
`SchoolAtmosphere`) was found partway through this project and
explicitly rejected by the user — "there is no need for a survey." It
has no bearing on this bot and should not be revived or referenced when
implementing this design.
