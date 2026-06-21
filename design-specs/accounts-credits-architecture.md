# Technical Architecture Spec — User Accounts + Stripe Coin-Bank Wallet

**Status:** DESIGN ONLY (no implementation). Architect review artifact.
**Scope:** Phase 1 = accounts + wallet + Stripe→coins. The per-generation **deduction seam** is *specified but unwired* (Phase 2 wires it). 100 coins = $1.00 USD.

---

## 0. Grounding — current state (verified against `main.py`)

- Single-process FastAPI app (`main.py`); static frontend mounted **last** at `/` (`app.mount("/", StaticFiles(...))`, line ~1503). Any new API routes MUST be declared *before* that mount.
- **No database.** Persistent state today: `config.json` (API keys via `settings_store.py`), `gallery/*.json` + `gallery/{images,models}.json` manifests, `output/` PNGs + `output/figures/*.glb`.
- **No auth.** Every endpoint is open. `CORSMiddleware` is wide-open (`allow_origins=["*"]`) — must be tightened when cookies/credentials are involved.
- Frontend is vanilla JS; every page sets `const API = window.location.origin;` and calls `fetch(`${API}/...`)`. **Same-origin** — the frontend is served by the same FastAPI process. This is the key fact that drives the auth-token decision below.
- Generation endpoints that will *eventually* debit coins: `/generate`, `/generate/stream` (SSE), `/decompose`, `/recheck-readings`, `/figure/generate`, `/figure/generate-from-image`, `/practice-sheet` (cloud). **Free (never debit):** `/practice-sheet/local`, export/print (client-side), `/image/{f}`, `/figure/model/{f}`, `/gallery*` reads.
- Async jobs (`/figure/*`, `/practice-sheet`) run in **daemon threads** with in-memory job stores (`_figure_jobs`, `_practice_jobs`). This matters for the refund-on-failure design: the failure happens *inside a worker thread*, not the request handler.

---

## 1. Auth recommendation

### Recommendation: **Clerk**

| Criterion | Clerk | Supabase Auth |
|---|---|---|
| FastAPI token verification | Verify Clerk session JWT against Clerk JWKS (`https://<frontend-api>/.well-known/jwks.json`) with `PyJWT[crypto]`. Stateless, no DB round-trip. | Verify Supabase JWT with the project JWT secret (HS256) **or** JWKS. Also stateless. |
| Frontend SDK for vanilla JS | `@clerk/clerk-js` loads via a single `<script>` (CDN) — **no build step**, fits this no-bundler frontend exactly. Provides `Clerk.session.getToken()`. | `@supabase/supabase-js` is ESM; usable via CDN `esm.sh` import but pairs more naturally with a bundler. Works, slightly more friction. |
| Cost / free tier | Generous free tier (MAU-based); paid tiers predictable. | Auth included in Supabase project (we're already paying for the DB). Marginally cheaper since it's bundled. |
| Lock-in | Higher (Clerk owns identity; user table lives in Clerk). Mitigated because **we keep our own `profiles` row keyed by the external auth id** — see §2. | Lower — auth user lives in the same Postgres we own (`auth.users`). |
| Drop-in UI | Prebuilt `<SignIn/>` / `<UserButton/>` components, hosted pages — fastest to ship a polished flow with zero custom UI. | Lower-level; we'd build more UI or use the hosted Supabase UI. |

**Why Clerk wins for THIS stack:** the deciding factor is the **no-build-step vanilla-JS frontend served same-origin by FastAPI**. Clerk's `clerk-js` CDN script + hosted sign-in pages let us add auth with one `<script>` per page and zero bundler — matching the existing "hand-copied identical HTML" discipline. We pay a small lock-in premium, neutralized by storing our own `profiles` row keyed on `clerk_user_id` (Clerk is never the source of truth for wallet/coins — Postgres is).

> **If the team prefers zero new vendor** (Supabase already chosen for DB): Supabase Auth is an acceptable fallback. The data model and deduction seam in this doc are **auth-provider-agnostic** — only the `verify_token()` body and the frontend script tag change. We isolate the provider behind one module (`auth.py`) so swapping is a contained change.

### FastAPI verification: a `current_user` dependency

A new `auth.py` exposes one FastAPI dependency. Token comes from the `Authorization: Bearer <jwt>` header (see frontend §1b).

```python
# auth.py  (SKETCH — design only)
import jwt                      # PyJWT[crypto]
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request

_JWKS = PyJWKClient(CLERK_JWKS_URL)   # cached, refreshes keys internally

class CurrentUser(BaseModel):
    auth_id: str          # Clerk 'sub' claim — external identity
    email: str | None

def _verify_token(token: str) -> CurrentUser:
    signing_key = _JWKS.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token, signing_key,
        algorithms=["RS256"],
        audience=CLERK_AUD,      # configured; reject tokens minted for other apps
        options={"require": ["exp", "sub"]},
    )
    return CurrentUser(auth_id=claims["sub"], email=claims.get("email"))

async def current_user(request: Request) -> CurrentUser:
    hdr = request.headers.get("authorization", "")
    if not hdr.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        user = _verify_token(hdr[7:])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    # Lazily ensure a profiles+wallet row exists for first-seen users (idempotent upsert)
    await db.ensure_profile(user.auth_id, user.email)
    return user

# Optional variant for endpoints that work logged-out today but want the user if present:
async def optional_user(request: Request) -> CurrentUser | None: ...
```

**Protected vs public in Phase 1:**
- **Auth-gated now:** `GET /wallet`, `POST /billing/checkout`. (Wallet/billing are the only *new* surfaces.)
- **NOT gated now:** all existing generation/gallery routes stay open in Phase 1 — gating + deduction is Phase 2. (Keeps Phase 1 shippable without breaking the current open app.)
- **Never gated:** `POST /stripe/webhook` is authenticated by **Stripe signature**, not user JWT (it's a server-to-server call — no `current_user`).

### 1b. Frontend: attaching the token (keep self-served frontend working)

The frontend stays served by FastAPI at `/`. Per page we add (non-module, before the page script, mirroring the `shared_inputs.js` pattern):

```html
<script src="https://<clerk-frontend-api>/npm/@clerk/clerk-js@5/dist/clerk.browser.js"
        data-clerk-publishable-key="pk_live_..."></script>
<script src="auth_client.js"></script>   <!-- exposes window.Auth -->
```

`auth_client.js` (new, plain script — matches `shared_inputs.js` / `SharedInputs` convention):

```js
window.Auth = (function () {
  async function ready()  { await Clerk.load(); return Clerk; }
  async function token()  { return (await ready()).session?.getToken() ?? null; }
  // Drop-in wrapper so existing fetch sites change minimally:
  async function authFetch(url, opts = {}) {
    const t = await token();
    const headers = new Headers(opts.headers || {});
    if (t) headers.set('Authorization', 'Bearer ' + t);
    return fetch(url, { ...opts, headers });
  }
  function isSignedIn() { return !!Clerk?.user; }
  return { ready, token, authFetch, isSignedIn, signIn: () => Clerk.openSignIn() };
})();
```

- **Phase 1 frontend touch is tiny:** add the two script tags + a sign-in/`UserButton` mount + a wallet-balance badge in the header. Existing `fetch(`${API}/...`)` calls are **left untouched** in Phase 1 (those endpoints stay open). In Phase 2, generation calls migrate from `fetch` → `Auth.authFetch` so the JWT rides along.
- **Bearer header, not cookies** → we keep `Authorization` header-based, which means **CORS can stay simple and we avoid CSRF** (no ambient cookie credentials). Same-origin already, so no CORS change is forced; but if we ever split origins, header-bearer scales. We will still **tighten `allow_origins`** off `"*"` to the known app origin(s) as hygiene.

---

## 2. Data model (Postgres / Supabase)

Design principles:
- **External identity ↔ local profile mapping.** We do not duplicate Clerk's user table; we key everything on `auth_id` (Clerk `sub`).
- **Append-only `coin_ledger`** is the source of truth. **`wallets.balance` is a cached, transactionally-maintained column** (see recommendation below).
- **`stripe_events`** gives webhook idempotency.
- All money/coin mutations happen in **one DB transaction** (ledger insert + balance update + event mark), via `SELECT ... FOR UPDATE` on the wallet row.

### Balance: derived vs cached → **Recommendation: cached column, maintained transactionally**

Pure-derived (`SUM(amount)` over the ledger) is the most auditable but gets slow and forces a full-scan on the hottest read (`GET /wallet`) and on every future debit. We instead keep `wallets.balance` as a **denormalized cache** that is only ever written **inside the same transaction that appends the ledger row**, under a row lock. The ledger remains the audit source of truth; `balance` is reproducible by replay (and a periodic invariant check `balance == SUM(ledger.amount)` can run as a guardrail). This gives O(1) reads/debits with full auditability.

### DDL sketch

```sql
-- 2.1 Profiles: local mirror keyed on the external auth provider id.
create table profiles (
  id           uuid primary key default gen_random_uuid(),
  auth_id      text unique not null,            -- Clerk 'sub'
  email        text,
  created_at   timestamptz not null default now()
);

-- 2.2 Wallet: one per profile. balance is a transactionally-maintained cache.
create table wallets (
  id           uuid primary key default gen_random_uuid(),
  profile_id   uuid not null unique references profiles(id) on delete cascade,
  balance      bigint not null default 0 check (balance >= 0),  -- coins; never negative
  updated_at   timestamptz not null default now()
);

-- 2.3 Append-only ledger — the audit source of truth. NEVER updated/deleted.
create type ledger_kind as enum ('purchase', 'debit', 'refund', 'adjustment', 'grant');

create table coin_ledger (
  id            bigint generated always as identity primary key,
  wallet_id     uuid not null references wallets(id),
  kind          ledger_kind not null,
  amount        bigint not null,                -- +credit / -debit, in coins
  balance_after bigint not null,                -- snapshot for audit/replay
  reason        text not null,                  -- e.g. 'stripe_purchase', 'generate_stream'
  -- Cross-references (nullable; depends on kind):
  stripe_event_id text,                         -- for purchases
  generation_ref  text,                         -- Phase 2: job_id / request id for debits
  idempotency_key text unique,                  -- prevents double-apply of a given op
  created_at    timestamptz not null default now()
);
create index on coin_ledger (wallet_id, created_at desc);

-- 2.4 Stripe webhook idempotency / audit.
create table stripe_events (
  event_id     text primary key,                -- Stripe 'evt_...' id
  type         text not null,
  status       text not null default 'received',-- received | applied | ignored | error
  payload      jsonb,
  received_at  timestamptz not null default now(),
  applied_at   timestamptz
);

-- 2.5 Server-authoritative coin packages (NOT client-trusted pricing). See §3.
create table coin_packages (
  id            text primary key,               -- 'pack_5usd'
  display_name  text not null,
  price_cents   integer not null,               -- USD cents charged via Stripe
  coins         bigint not null,                -- coins granted (price_cents * 100 / 100 = price_cents)
  active        boolean not null default true
);
```

**Invariant:** `coins = price_cents` (because 100 coins = $1 = 100 cents → 1 coin per cent). Encoding it as a stored column (not derived in code) keeps room for promo packs (e.g. "$5 → 600 coins bonus") without changing the formula at the call site.

**Idempotency keys:**
- Purchase credit: `idempotency_key = 'stripe:' || event_id` (one credit per Stripe event, enforced by both the unique `idempotency_key` and the `stripe_events` PK).
- Future debit (Phase 2): `idempotency_key = 'debit:' || generation_ref` (one debit per generation request id; safe under client retries).
- Refund (Phase 2 failure path): `idempotency_key = 'refund:' || generation_ref`.

---

## 3. Stripe flow

```
[Client]  POST /billing/checkout {package_id}        (auth-gated; current_user)
            -> server looks up coin_packages[package_id]  (price/coins server-side ONLY)
            -> stripe.checkout.Session.create(
                 mode='payment',
                 line_items=[{price_data from coin_packages, qty 1}],
                 success_url=APP_URL + '/wallet.html?status=success',
                 cancel_url =APP_URL + '/wallet.html?status=cancel',
                 client_reference_id = profile.id,            # who to credit
                 metadata={profile_id, package_id, coins},    # echoed back in webhook
               )
            <- { checkout_url }   (client redirects browser to Stripe-hosted page)

[Stripe]  user pays on Stripe-hosted checkout

[Stripe -> server]  POST /stripe/webhook   (signed; NO user JWT)
            -> verify signature (stripe.Webhook.construct_event)
            -> on 'checkout.session.completed' (and only when payment_status=='paid'):
                 BEGIN TRANSACTION
                   INSERT stripe_events(event_id,...) ON CONFLICT DO NOTHING   -- idempotency gate
                   if not inserted (already applied) -> COMMIT, return 200      -- dedup short-circuit
                   SELECT wallet FOR UPDATE where profile_id = metadata.profile_id
                   coins = coin_packages[metadata.package_id].coins   -- re-derive server-side, ignore any client value
                   UPDATE wallets SET balance = balance + coins
                   INSERT coin_ledger(kind='purchase', amount=+coins, balance_after,
                                      reason='stripe_purchase', stripe_event_id,
                                      idempotency_key='stripe:'||event_id)
                   UPDATE stripe_events SET status='applied', applied_at=now()
                 COMMIT
            <- 200   (always 200 on handled/duplicate; non-2xx only on transient server error so Stripe retries)
```

**Coins are granted ONLY here** — never on the `success_url` redirect (the client never reports payment success to our API). The success page just shows "Payment received — refreshing balance" and re-fetches `GET /wallet`.

**Idempotency (two layers):**
1. `stripe_events.event_id` PK + `INSERT ... ON CONFLICT DO NOTHING` → Stripe retries (it sends each event possibly multiple times) never double-credit.
2. `coin_ledger.idempotency_key` unique (`'stripe:'||event_id`) → defense in depth even if the events table is bypassed.

**Signature verification:** `stripe.Webhook.construct_event(raw_body, sig_header, STRIPE_WEBHOOK_SECRET)`. MUST read the **raw request body** (FastAPI: `await request.body()`), not the parsed JSON, or the HMAC check fails. Reject (400) on `SignatureVerificationError`.

**Package → coins mapping is server-side only.** The client sends `package_id`; the server reads `coin_packages` for price and coins. The webhook re-derives `coins` from `metadata.package_id` against the same table — **never trusts a `coins` value from the client or even blindly from metadata** (metadata is informational; the table is authoritative).

**Return URLs:** `success_url` / `cancel_url` point at a new `wallet.html` (or an existing page) on `APP_URL` (env-configured absolute origin), carrying only a non-authoritative `?status=` hint.

---

## 4. Wallet API

```
GET /wallet                          (Depends(current_user))
  -> resolve profile by auth_id, load wallet
  <- {
       "balance": 1240,                       # coins, from wallets.balance (cached)
       "history": [                            # newest first, paginated
          {"id": 987, "kind":"purchase", "amount": 500, "balance_after": 1240,
           "reason":"stripe_purchase", "created_at":"..."},
          {"id": 986, "kind":"debit", "amount": -8, "balance_after": 740,
           "reason":"generate_stream", "created_at":"..."}
       ],
       "next_cursor": "986"                    # for pagination
     }

GET /billing/packages                 (public or current_user — pricing display)
  <- { "packages": [ {"id":"pack_5usd","display_name":"$5 — 500 coins","price_cents":500,"coins":500}, ... ] }
```

History reads from `coin_ledger` ordered `created_at desc` with cursor pagination. Balance is the cached column (consistent with the ledger by construction).

---

## 5. THE DEDUCTION SEAM (design only — NOT wired in Phase 1)

**Goal:** Phase 2 is literally "add `Depends(charge_coins(N))` to each generation endpoint" with the SSE path getting a slightly richer context-manager form. Nothing in Phase 1 touches the generation handlers.

### 5a. Cost configuration

A server-side cost table (env- or DB-backed; start with a Python dict in a new `pricing.py`, graduate to a DB table if it needs runtime edits via Settings):

```python
# pricing.py (SKETCH)
GENERATION_COSTS = {        # coins per call
  "generate":            5,
  "generate_stream":     5,
  "decompose":          30,   # Opus call — most expensive
  "recheck_readings":   20,
  "figure_generate":    40,   # Meshy 3D
  "figure_from_image":  40,
  "practice_sheet":     15,   # cloud (code-exec); local is FREE
}
```

Costs are **never** sent by the client. The endpoint names its own cost from this table.

### 5b. The reusable primitives

Two shapes, sharing one core `wallet.reserve()` transaction:

**(i) Simple dependency — for synchronous, fail-fast endpoints** (`/generate`, `/decompose`, `/recheck-readings`):

```python
# wallet.py (SKETCH — design only)
def charge_coins(cost: int, reason: str):
    async def _dep(user: CurrentUser = Depends(current_user)) -> "Charge":
        # ONE transaction: lock wallet, check balance, debit, ledger-insert.
        charge = await wallet_reserve(user.auth_id, cost, reason,
                                      generation_ref=new_request_id())
        if charge is None:
            raise HTTPException(402, "Insufficient coins")   # 402 Payment Required
        return charge          # carries .generation_ref, .cost, .wallet_id
    return _dep

# Endpoint usage in Phase 2 (illustrative — DO NOT ADD NOW):
# @app.post("/decompose")
# def decompose(req: DecomposeRequest, charge: Charge = Depends(charge_coins(30, "decompose"))):
#     try:
#         result = ...do work...
#         return result
#     except Exception:
#         await wallet_refund(charge)   # credit-back on failure
#         raise
```

`wallet_reserve()` is the atomic core:

```python
async def wallet_reserve(auth_id, cost, reason, generation_ref) -> Charge | None:
    async with db.transaction():
        w = await db.fetch("SELECT * FROM wallets w JOIN profiles p ... "
                           "WHERE p.auth_id=$1 FOR UPDATE", auth_id)
        if w.balance < cost:
            return None                      # no debit, transaction rolls back cleanly
        new_balance = w.balance - cost
        await db.execute("UPDATE wallets SET balance=$1 WHERE id=$2", new_balance, w.id)
        await db.execute(
          "INSERT INTO coin_ledger(wallet_id,kind,amount,balance_after,reason,"
          "generation_ref,idempotency_key) VALUES ($1,'debit',$2,$3,$4,$5,$6)",
          w.id, -cost, new_balance, reason, generation_ref, 'debit:'+generation_ref)
    return Charge(wallet_id=w.id, cost=cost, generation_ref=generation_ref)

async def wallet_refund(charge: Charge):
    async with db.transaction():
        w = await db.fetch("SELECT * FROM wallets WHERE id=$1 FOR UPDATE", charge.wallet_id)
        new_balance = w.balance + charge.cost
        await db.execute("UPDATE wallets SET balance=$1 WHERE id=$2", new_balance, w.id)
        await db.execute(
          "INSERT INTO coin_ledger(wallet_id,kind,amount,balance_after,reason,"
          "generation_ref,idempotency_key) VALUES ($1,'refund',$2,$3,'refund',$4,$5)",
          w.id, +charge.cost, new_balance, charge.generation_ref,
          'refund:'+charge.generation_ref)   # unique key => refund applied at most once
```

**Pattern: charge-BEFORE, refund-on-error.** The debit commits before any provider (Gemini/Claude/Meshy) call. If generation throws, we append a compensating **refund** ledger row (not a delete — the ledger stays append-only and auditable). The `'refund:'+ref` unique idempotency key guarantees a single refund even under retries.

### 5c. SSE path — the critical case (`/generate/stream`)

The hard part: the actual work runs in a **daemon thread** (`run()` inside `generate_stream`), and the response has already started streaming. Design:

1. **Charge synchronously, before spawning the thread** — in the request handler, *before* `threading.Thread(...).start()`. If the wallet lacks coins, return **402 immediately** (no SSE stream opened, no thread). This satisfies "deduct atomically before the background thread starts."

   ```python
   # Phase 2 sketch — NOT added now:
   # @app.post("/generate/stream")
   # async def generate_stream(req: GenerateRequest,
   #                           charge: Charge = Depends(charge_coins(5, "generate_stream"))):
   #     # charge already committed here. Pass charge into the worker for refund-on-error.
   #     def run():
   #         try: ...generate...; queue.put({"done": True, ...})
   #         except Exception as e:
   #             schedule_refund(charge)          # thread-safe: enqueue to the event loop
   #             queue.put({"error": str(e), "refunded": charge.cost})
   ```

2. **Refund from the worker thread** must hop back to async/DB safely. Two acceptable mechanisms:
   - Use `loop.call_soon_threadsafe(...)` to schedule `wallet_refund(charge)` as a task on the main event loop (the loop ref is already captured in `generate_stream` as `loop`), **or**
   - Run the refund through a sync DB path (psycopg sync connection) directly in the worker thread.
   The SSE failure event is extended to `{"error": ..., "refunded": <coins>}` so the client can show "coins returned".

3. **Same model for the other thread-worker jobs** (`/figure/generate`, `/practice-sheet` cloud): charge in the **route handler before `_job_create` / thread start**; on the worker's `except` path (which already sets `stage:"error"`), also enqueue a refund and surface `"refunded"` in the job record so the polling client can display it.

**Why charge-before (not charge-on-success):** prevents a user from opening many concurrent SSE streams to outrun the balance check (each `wallet_reserve` takes a row lock and re-reads balance, so concurrent charges serialize and a 402 fires as soon as the balance would go negative). Refund-on-failure keeps it fair when our provider call fails.

### 5d. Seam contract summary (what Phase 2 consumes)

```
charge_coins(cost: int, reason: str) -> FastAPI dependency
    yields Charge{ wallet_id, cost, generation_ref, reason }
    raises HTTPException(402) when balance < cost
    side effect: atomic debit + ledger('debit') committed BEFORE the endpoint body runs

wallet_refund(charge: Charge) -> None
    atomic credit-back + ledger('refund'); idempotent on generation_ref
    callable from sync worker threads (via call_soon_threadsafe or a sync DB conn)

GENERATION_COSTS: dict[endpoint_name -> coins]   (server-authoritative; client never sends cost)
```

Phase 2 work = add `Depends(charge_coins(GENERATION_COSTS[name], name))` to the 7 generation routes, add `wallet_refund` to their failure paths (handler `except` for sync routes; worker `except` for SSE/job routes), and migrate frontend generation `fetch` → `Auth.authFetch`. **None of this is added in Phase 1.**

---

## 6. Security

- **Webhook signature verification** with `STRIPE_WEBHOOK_SECRET` over the **raw body**; reject unsigned/invalid (400). The webhook is the *only* path that grants coins.
- **No client-side coin grants.** Success redirect is cosmetic; the client cannot mint coins.
- **Server-authoritative pricing.** `coin_packages` (DB) and `GENERATION_COSTS` (server) are never taken from the request body. Webhook re-derives coins from `package_id` → table.
- **All wallet/billing endpoints auth-gated** via `Depends(current_user)`; `/stripe/webhook` is signature-gated (no JWT).
- **JWT validation:** verify signature against provider JWKS, check `aud` and `exp`, require `sub`. Reject tokens minted for other apps.
- **CORS:** tighten `allow_origins` from `"*"` to the known app origin(s) before shipping auth (currently wide open). Header-bearer tokens (not cookies) avoid CSRF and keep us off ambient credentials.
- **Secrets handling — extend the existing model, don't fork it.** New secrets: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY` (publishable is non-secret), `CLERK_SECRET_KEY` / `CLERK_PUBLISHABLE_KEY` / `CLERK_JWKS_URL` / `CLERK_AUD`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
  - These are **infrastructure secrets**, not user-editable API keys → they belong in **`.env` / host secret store (Railway/Fly)**, loaded via `config.py` (extend it with `os.getenv`), **NOT** in `config.json`/Settings UI. `config.json` + `settings_store.py` stay scoped to the three *generation* provider keys (Anthropic/Gemini/Meshy) a self-hosting operator pastes in. Wallet/billing secrets must not be runtime-editable from the browser.
  - The **Supabase service-role key** (bypasses RLS) is used only server-side for ledger writes; never exposed to the frontend. The frontend, if it ever talks to Supabase directly, uses the anon key + RLS — but in this design the frontend talks **only to FastAPI**, so the service key never leaves the server.
- **Negative-balance guard** at the DB level: `wallets.balance >= 0` CHECK constraint is a backstop; the app-level `FOR UPDATE` + balance check is the primary gate.

---

## 7. Integration & rollout

### Route placement (`main.py`)
All new routes declared **before** `app.mount("/", StaticFiles(...))` (line ~1503), alongside the other API routes:
```
POST /billing/checkout          (current_user)
GET  /billing/packages          (public)
GET  /wallet                    (current_user)
POST /stripe/webhook            (signature-gated; reads raw body)
```
New `wallet.html` / `wallet.js` (+ optional account UI) live in `frontend/` and are served by the existing static mount — no routing change.

### New dependencies (`requirements.txt`)
```
stripe>=9.0
PyJWT[crypto]>=2.8            # JWT verification (provider-agnostic)
# DB access — pick ONE (see below):
supabase>=2.0                # OR
# asyncpg>=0.29 + SQLAlchemy>=2.0
```

### DB access choice → **Recommendation: `asyncpg` (+ a thin query layer), not the Supabase Python client**
- The Supabase Python client is REST/PostgREST-oriented and awkward for **`SELECT ... FOR UPDATE` inside an explicit transaction** — which the wallet reserve/refund core *requires*. `asyncpg` gives real transactions and row locks with minimal overhead, and connects to Supabase Postgres directly via `SUPABASE_DB_URL`.
- SQLAlchemy 2.0 async is fine if the team wants an ORM/migrations story (Alembic); for this small schema, `asyncpg` + raw SQL + a migrations folder is leaner. Either way, **avoid the PostgREST client for the money path.**
- **Connection management in FastAPI lifespan:** create an `asyncpg` pool in the existing `lifespan()` (`main.py` already has one, lines 39–45), store on `app.state.db`, close on shutdown. The deduction seam and webhook acquire connections from this pool. The daemon-thread workers (figure/practice) that need to refund use either `call_soon_threadsafe` onto the main loop **or** a separate small sync `psycopg` connection — call this out as a Phase-2 implementation detail.

### Local-dev story
- **Stripe CLI for webhooks:** `stripe listen --forward-to localhost:8000/stripe/webhook` gives a local `whsec_...` signing secret; `stripe trigger checkout.session.completed` to exercise the credit path offline.
- **SQLite fallback for local dev:** *Yes, recommended* — keep the schema portable. The DDL above is near-portable; the only Postgres-isms are `gen_random_uuid()`, `enum`, `jsonb`, `generated always as identity`. Provide a SQLite-compatible variant (TEXT uuids via app-generated values, INTEGER PK autoincrement, TEXT for jsonb, CHECK constraints work). Gate via `DATABASE_URL` (sqlite:///./dev.db vs the Supabase URL). Transactions + `FOR UPDATE` semantics differ (SQLite serializes writes anyway), so the wallet core stays correct; just document that `FOR UPDATE` is a no-op on SQLite (acceptable single-process locally). Use SQLAlchemy if we want one code path across both; raw SQL if we keep two small dialect files. **Recommendation:** if cross-DB matters, lean SQLAlchemy 2.0 async to get both dialects for free; otherwise asyncpg-only and skip SQLite (run a local Postgres in Docker).

### Coexistence with current single-process / hosting move
- Today everything is one process + local files. Adding Postgres means the app is **no longer fully self-contained** — note this for self-hosters (they now need a DB). Mitigate: keep the **whole accounts/wallet subsystem behind a feature flag** (`BILLING_ENABLED`); when off, the app behaves exactly as today (open, no DB required). Phase 1 ships with the flag, default off for OSS/self-host, on for the hosted deployment.
- **Railway/Fly move:** the DB pool + secrets-from-env model is exactly what those platforms want (managed Postgres add-on or Supabase URL; secrets in their vault). `output/`, `gallery/`, `config.json` on local disk become the **stateful wart** — fine on a single persistent-volume instance, but it blocks horizontal scaling.

### Per-user namespacing of `gallery/` & `output/` — **noted future step, NOT Phase 1**
Currently global shared dirs. Eventual design: prefix paths by `profile_id` (e.g. `output/{profile_id}/...`, `gallery/{profile_id}/...`) and add `profile_id` to the gallery manifests, OR move gallery metadata into Postgres tables (`gallery_images`, `gallery_books`, `gallery_models`) keyed by `profile_id` while files stay on object storage (S3/Supabase Storage). This is the natural companion to the hosting move (object storage replaces local disk) but is **explicitly out of Phase 1 scope**. Phase 1 must simply **not cement new global state** — the wallet/ledger is already per-user, so it adds no new sharing problem.

---

## 8. Phase boundary

| | Phase 1 (this build) | Phase 2 (later) |
|---|---|---|
| Accounts (Clerk) + `current_user` dep | ✅ build | — |
| `profiles`/`wallets`/`coin_ledger`/`stripe_events`/`coin_packages` schema | ✅ build | — |
| `POST /billing/checkout`, `GET /billing/packages`, `GET /wallet` | ✅ build | — |
| `POST /stripe/webhook` → atomic coin credit | ✅ build | — |
| Frontend: sign-in, header balance badge, `wallet.html`, `auth_client.js` | ✅ build | — |
| `charge_coins` / `wallet_reserve` / `wallet_refund` / `GENERATION_COSTS` | 📐 **specified, code-stubbed, but NOT wired to any endpoint** | ✅ wire |
| `Depends(charge_coins(...))` on the 7 generation routes | ❌ not added | ✅ add |
| Refund-on-failure in SSE/job workers | ❌ not added | ✅ add |
| Generation routes gated by `current_user` | ❌ stay open | ✅ gate |
| Frontend generation `fetch` → `Auth.authFetch` | ❌ unchanged | ✅ migrate |
| Per-user `gallery/`/`output/` namespacing + object storage | ❌ | 🔜 future |

**Definition of done for Phase 1:** a signed-in user can buy a coin package via Stripe Checkout, the webhook atomically credits coins, and `GET /wallet` shows the new balance + purchase history. Generation remains free/open. The deduction seam exists as a tested, unwired module so Phase 2 is additive only.

---

## Architect verdict

- **Feasibility:** Go with changes.
- **Top risks:** (1) SSE refund-from-thread correctness — must use `call_soon_threadsafe` or a sync DB conn, not touch the async pool from the worker thread; (2) webhook raw-body handling (parsed body breaks signature check); (3) the new hard DB dependency erodes the "single-process, no-DB, self-hostable" property — mitigated by the `BILLING_ENABLED` flag; (4) CORS is currently `"*"` and must be tightened with auth; (5) Clerk lock-in — mitigated by the local `profiles` mapping and an isolated `auth.py`.
- **Required before Phase 2:** the seam module must ship with unit tests proving atomic debit, insufficient-balance 402, and idempotent refund — so wiring is purely additive.
