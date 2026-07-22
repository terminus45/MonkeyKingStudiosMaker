"""billing_db.py — SQLite-backed wallet/ledger store for Phase 1.

Uses stdlib sqlite3 only. Schema is designed to be Postgres-portable:
  - INTEGER PK (Postgres: BIGINT GENERATED ALWAYS AS IDENTITY)
  - TEXT for UUIDs (Postgres: UUID DEFAULT gen_random_uuid())
  - REAL amounts are avoided (coins are integers)
  - CHECK constraints work on both dialects
  - BEGIN IMMEDIATE → Postgres: BEGIN + SELECT ... FOR UPDATE (same serialisation intent)

Production swap notes:
  - Replace sqlite3 with asyncpg (+ connection pool in lifespan) or SQLAlchemy 2 async.
  - Replace BEGIN IMMEDIATE with explicit BEGIN + SELECT ... FOR UPDATE on wallet row.
  - Replace uuid.uuid4() TEXT PKs with gen_random_uuid() in DDL.
  - Add created_at DEFAULT now() (Postgres timestamptz) vs CURRENT_TIMESTAMP (SQLite TEXT).

This module is only imported when BILLING_ENABLED=true (guarded in main.py lifespan + route
registration). It must never be imported at module-level in main.py.
"""

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import DATABASE_URL

# --- Exceptions ---

class InsufficientCoins(Exception):
    """Raised by charge_coins when wallet balance < requested cost."""
    def __init__(self, balance: int, cost: int):
        self.balance = balance
        self.cost = cost
        super().__init__(f"Insufficient coins: balance={balance}, cost={cost}")


# --- Connection management ---

_db_lock = threading.Lock()
_db_path: Optional[str] = None


def _get_db_path() -> str:
    """Resolve the SQLite file path from DATABASE_URL.

    Accepts:
      sqlite:///./billing.db   -> ./billing.db
      sqlite:///billing.db     -> billing.db
      /absolute/path/to/db     -> that path (no prefix required)
    """
    url = DATABASE_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url


def _connect() -> sqlite3.Connection:
    """Open a new SQLite connection with sensible settings."""
    path = _get_db_path()
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# --- Schema init ---

_DDL = """
CREATE TABLE IF NOT EXISTS profiles (
    id         TEXT PRIMARY KEY,
    auth_id    TEXT UNIQUE NOT NULL,
    email      TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS wallets (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    balance    INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS coin_ledger (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id       TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL CHECK (kind IN ('purchase','debit','refund','adjust')),
    amount           INTEGER NOT NULL,
    balance_after    INTEGER NOT NULL,
    reason           TEXT NOT NULL DEFAULT '',
    stripe_event_id  TEXT,
    generation_ref   TEXT,
    idempotency_key  TEXT UNIQUE,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ledger_profile_created
    ON coin_ledger (profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id   TEXT PRIMARY KEY,
    status     TEXT NOT NULL DEFAULT 'received',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def init_db() -> None:
    """Create tables if they do not exist. Call once at app startup (inside lifespan)."""
    with _connect() as conn:
        conn.executescript(_DDL)


# --- Profile / wallet helpers ---

def get_or_create_profile(auth_id: str, email: Optional[str] = None) -> str:
    """Return profile_id for auth_id, creating profile + wallet rows if first seen.

    Idempotent: calling multiple times with the same auth_id always returns the same id.
    Uses BEGIN IMMEDIATE so two concurrent first-logins for the same auth_id don't race.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id FROM profiles WHERE auth_id = ?", (auth_id,)
        ).fetchone()
        if row:
            profile_id = row["id"]
            conn.execute("COMMIT")
        else:
            profile_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO profiles (id, auth_id, email) VALUES (?, ?, ?)",
                (profile_id, auth_id, email),
            )
            conn.execute(
                "INSERT INTO wallets (profile_id, balance) VALUES (?, 0)",
                (profile_id,),
            )
            conn.execute("COMMIT")
        return profile_id
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_wallet(profile_id: str) -> dict:
    """Return {balance, history} for profile_id.

    history: list of ledger rows, newest first (last 50 entries).
    """
    conn = _connect()
    try:
        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if wallet is None:
            return {"balance": 0, "history": []}

        rows = conn.execute(
            """SELECT id, kind, amount, balance_after, reason,
                      stripe_event_id, generation_ref, created_at
               FROM coin_ledger
               WHERE profile_id = ?
               ORDER BY id DESC
               LIMIT 50""",
            (profile_id,),
        ).fetchall()

        history = [dict(r) for r in rows]
        return {"balance": wallet["balance"], "history": history}
    finally:
        conn.close()


# --- Credit / debit operations ---

def credit_coins(
    profile_id: str,
    amount: int,
    reason: str,
    *,
    stripe_event_id: Optional[str] = None,
    idempotency_key: str,
) -> int:
    """Credit *amount* coins to profile_id's wallet.

    Atomically inserts a ledger('purchase') row and increments balance.
    Idempotent on idempotency_key: if the key already exists, returns current balance
    without modifying anything.

    Returns the new (or current) balance.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency check
        exists = conn.execute(
            "SELECT id FROM coin_ledger WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if exists:
            balance = conn.execute(
                "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            conn.execute("COMMIT")
            return balance["balance"] if balance else 0

        # Read current balance
        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if wallet is None:
            raise ValueError(f"No wallet found for profile_id={profile_id!r}")

        new_balance = wallet["balance"] + amount

        # Update wallet
        conn.execute(
            "UPDATE wallets SET balance = ? WHERE profile_id = ?",
            (new_balance, profile_id),
        )

        # Append ledger row
        conn.execute(
            """INSERT INTO coin_ledger
               (profile_id, kind, amount, balance_after, reason,
                stripe_event_id, idempotency_key)
               VALUES (?, 'purchase', ?, ?, ?, ?, ?)""",
            (profile_id, amount, new_balance, reason, stripe_event_id, idempotency_key),
        )

        conn.execute("COMMIT")
        return new_balance
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def charge_coins(
    profile_id: str,
    cost: int,
    reason: str,
    *,
    generation_ref: str,
) -> int:
    """Atomically debit *cost* coins from profile_id's wallet.

    Raises InsufficientCoins if balance < cost.
    Returns new balance.

    SEAM (Phase 1): This function is exported and fully tested but NOT called by any
    generation endpoint. Phase 2 wires it via a FastAPI dependency (Depends(charge_coins(N))).
    """
    idempotency_key = f"debit:{generation_ref}"

    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency check
        exists = conn.execute(
            "SELECT id FROM coin_ledger WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if exists:
            balance = conn.execute(
                "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            conn.execute("COMMIT")
            return balance["balance"] if balance else 0

        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if wallet is None:
            raise ValueError(f"No wallet found for profile_id={profile_id!r}")

        if wallet["balance"] < cost:
            conn.execute("ROLLBACK")
            raise InsufficientCoins(balance=wallet["balance"], cost=cost)

        new_balance = wallet["balance"] - cost

        conn.execute(
            "UPDATE wallets SET balance = ? WHERE profile_id = ?",
            (new_balance, profile_id),
        )
        conn.execute(
            """INSERT INTO coin_ledger
               (profile_id, kind, amount, balance_after, reason,
                generation_ref, idempotency_key)
               VALUES (?, 'debit', ?, ?, ?, ?, ?)""",
            (profile_id, -cost, new_balance, reason, generation_ref, idempotency_key),
        )

        conn.execute("COMMIT")
        return new_balance
    except InsufficientCoins:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def refund_coins(
    profile_id: str,
    amount: int,
    reason: str,
    *,
    generation_ref: str,
) -> int:
    """Atomically credit *amount* coins back to profile_id's wallet (refund).

    Idempotent on generation_ref: a second call with the same ref is a no-op.
    Returns the new (or current) balance.

    SEAM (Phase 1): Exported and tested but NOT wired to any generation failure path.
    Phase 2 calls this from SSE worker / job worker exception handlers.
    """
    idempotency_key = f"refund:{generation_ref}"

    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency check
        exists = conn.execute(
            "SELECT id FROM coin_ledger WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if exists:
            balance = conn.execute(
                "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            conn.execute("COMMIT")
            return balance["balance"] if balance else 0

        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if wallet is None:
            raise ValueError(f"No wallet found for profile_id={profile_id!r}")

        new_balance = wallet["balance"] + amount

        conn.execute(
            "UPDATE wallets SET balance = ? WHERE profile_id = ?",
            (new_balance, profile_id),
        )
        conn.execute(
            """INSERT INTO coin_ledger
               (profile_id, kind, amount, balance_after, reason,
                generation_ref, idempotency_key)
               VALUES (?, 'refund', ?, ?, ?, ?, ?)""",
            (profile_id, amount, new_balance, reason, generation_ref, idempotency_key),
        )

        conn.execute("COMMIT")
        return new_balance
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def record_stripe_event(event_id: str) -> bool:
    """Insert a stripe_events row for event_id.

    Returns True if newly inserted (first time seen), False if already processed (dedup).
    Use the return value to short-circuit duplicate webhook deliveries.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO stripe_events (event_id, status) VALUES (?, 'received')",
                (event_id,),
            )
            conn.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            # PK conflict — already processed
            conn.execute("ROLLBACK")
            return False
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def update_stripe_event_status(event_id: str, status: str) -> None:
    """Update stripe_events.status (e.g. 'applied', 'error'). Best-effort."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE stripe_events SET status = ? WHERE event_id = ?",
            (status, event_id),
        )
        conn.commit()
    finally:
        conn.close()
