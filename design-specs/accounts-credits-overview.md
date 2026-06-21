# Accounts + Coin-Bank Credits — Design Overview (Phasing & Decisions)

Design-only. Companion to:
- `accounts-credits-ux.md` — UI/UX (header chip, Account/Wallet page, buy-coins flow)
- `accounts-credits-architecture.md` — backend architecture (auth, DB schema, Stripe webhook, deduction seam)

## Goal
Add simple user accounts + Stripe payments that fund a **coin bank at 100 coins per $1**.
**Build Phase 1 only; stop there.** Design — but do not build — the seam where every
generation later checks balance and deducts coins before running.

## Phase boundary
**Phase 1 — BUILD:** managed auth (email + Google), a Postgres-backed wallet, Stripe
Checkout for fixed coin packages, coins credited **only via the Stripe webhook**, and a
Wallet page + header balance chip to view balance & purchase history.

**Phase 2 — DESIGN ONLY NOW:** a reusable `charge_coins(cost)` FastAPI dependency
(charge-before-generate, refund-on-failure) that future generation endpoints adopt. Ships
in Phase 1 as a tested-but-**unwired** module. No generation endpoint changes behavior in
Phase 1. Per-user namespacing of `gallery/`/`output/` is deferred to Phase 2.

Line in one sentence: *Phase 1 moves money in and coins up and lets a user see both;
nothing reads a balance to allow/block a generation until Phase 2.*

## Coin / pricing model
- 100 coins = $1, fixed. Coins are the primary in-app unit.
- Fixed packages: **$5→500, $10→1,000, $20→2,000** (no arbitrary amounts in Phase 1).
- Coins **do not expire**. No in-app refunds/subscriptions/teams.

## Chargeable later (Phase 2), in adoption order
1. `/decompose` (simplest — single Claude call, no worker)
2. `/generate` then `/generate/stream` (SSE — charge in handler **before** the worker thread starts; refund on the `error` event)
3. `/figure/generate`(+`-from-image`), `/practice-sheet` (cloud) — charge before spawning the daemon worker; refund if the job ends in `error`
4. `/recheck-readings` (cheap; optional)
**Never charge:** `/practice-sheet/local`, HTML export/print (fully local/client-side).

## Acceptance criteria (Phase 1) — abridged
- New account starts at 0 coins; can buy a package via Stripe **test** Checkout.
- Coins credited **only** after the verified webhook (blocked webhook → balance stays 0).
- Webhook is **idempotent** (replaying an event credits once).
- `wallets.balance` always equals the signed sum of `coin_ledger`.
- A user can only read/credit their own wallet (server-enforced).
- No generation endpoint changes; free/local actions never touch the wallet.
- Static frontend mount still serves all pages; no route shadowed.

## Decisions made (2026-06-20)
- **Auth vendor — decided at BUILD TIME.** Both Supabase Auth (one vendor with the DB, Postgres RLS) and Clerk (best no-build-step vanilla-JS fit) remain valid; both verify a JWT via a `current_user` dependency and are isolated behind one `auth.py`, so the choice is a contained swap made when Phase 1 starts.
- **Hosting (Phase 1) — local + tunnel first.** Develop against the local server with Stripe CLI/ngrok for the webhook URL; defer the Railway/Fly.io move. (The remote Postgres can be hosted Supabase or local SQLite via `DATABASE_URL` during dev.)
- **Gating (Phase 1) — keep everything open.** Generation, local practice sheet, and export all work signed-out exactly as today. Accounts/wallet are purely additive until Phase 2.

## Still-open questions (lower priority / Phase-2)
1. **Phase-2 coin costs per generation** (image, decompose, figure, practice-cloud) — needed to size the cost map; informs package sizing.
2. **Stripe test-only for Phase 1?** Stripe Tax + automatic receipts on or off?
3. **Legacy data**: when per-user namespacing arrives, do today's global `gallery/`/`output/` artifacts get assigned to the owner account or treated as shared/legacy?

## Biggest architectural consequence
Phase 1 introduces a **hard Postgres dependency** (and a reachable webhook URL → likely a
hosting move), which erodes the app's current single-process / local / self-hostable
property. Mitigation (from the architecture spec): a `BILLING_ENABLED` flag so the app runs
exactly as today (no DB, no auth) when billing is off, and only requires the DB when on.
