"""tests/test_billing.py — Offline tests for the billing DB layer.

Tests run fully offline (no Stripe / network / real DB path).
Each test gets its own fresh in-memory SQLite DB via a fixture that monkeypatches
billing_db.DATABASE_URL and re-runs init_db().

Run: pytest tests/test_billing.py -q
"""

import os
import sys
import sqlite3
import tempfile
import threading
import uuid

import pytest

# Add repo root to path so `import billing_db` works from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need BILLING_ENABLED to be truthy so config exports the right flag,
# but billing_db does not check it — it is controlled by main.py's lifespan.
# Importing billing_db directly here is always fine.
import billing_db
from billing_db import InsufficientCoins


# ── Fixture: isolated temp DB per test ───────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets a brand-new SQLite file. Monkeypatches billing_db.DATABASE_URL."""
    db_path = str(tmp_path / "test_billing.db")
    monkeypatch.setattr(billing_db, "DATABASE_URL", db_path)
    billing_db.init_db()
    yield db_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_profile(auth_id="test_user", email=None):
    return billing_db.get_or_create_profile(auth_id, email)


def ledger_sum(profile_id: str) -> int:
    """Compute balance from raw ledger rows — independent balance recalculation."""
    path = billing_db._get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM coin_ledger WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    conn.close()
    return row["total"] if row else 0


def wallet_balance(profile_id: str) -> int:
    """Read the cached wallet.balance directly."""
    path = billing_db._get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT balance FROM wallets WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    conn.close()
    return row["balance"] if row else 0


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetOrCreateProfile:
    def test_creates_profile_and_wallet(self):
        pid = make_profile("alice")
        assert pid  # non-empty string

        data = billing_db.get_wallet(pid)
        assert data["balance"] == 0
        assert data["history"] == []

    def test_idempotent_same_auth_id(self):
        """Calling get_or_create_profile twice with the same auth_id returns the same id."""
        pid1 = billing_db.get_or_create_profile("bob", "bob@example.com")
        pid2 = billing_db.get_or_create_profile("bob", "bob@example.com")
        assert pid1 == pid2

    def test_idempotent_no_duplicate_wallet(self):
        """Multiple calls must not create multiple wallet rows."""
        for _ in range(5):
            billing_db.get_or_create_profile("carol")

        path = billing_db._get_db_path()
        conn = sqlite3.connect(path)
        count = conn.execute(
            "SELECT COUNT(*) FROM profiles WHERE auth_id = ?", ("carol",)
        ).fetchone()[0]
        wcount = conn.execute(
            "SELECT COUNT(*) FROM wallets"
        ).fetchone()[0]
        conn.close()
        assert count == 1
        assert wcount == 1

    def test_different_auth_ids_get_different_profiles(self):
        p1 = billing_db.get_or_create_profile("user_1")
        p2 = billing_db.get_or_create_profile("user_2")
        assert p1 != p2


class TestCreditCoins:
    def test_credits_coins_and_updates_balance(self):
        pid = make_profile()
        new_bal = billing_db.credit_coins(pid, 500, "stripe_purchase",
                                          idempotency_key="idem_1")
        assert new_bal == 500
        assert wallet_balance(pid) == 500

    def test_credit_is_idempotent_on_idempotency_key(self):
        """Double-apply with the same key credits exactly once."""
        pid = make_profile()
        key = "stripe:evt_test_001"

        bal1 = billing_db.credit_coins(pid, 1000, "stripe_purchase",
                                        idempotency_key=key)
        bal2 = billing_db.credit_coins(pid, 1000, "stripe_purchase",
                                        idempotency_key=key)

        assert bal1 == bal2 == 1000  # second call is a no-op
        assert wallet_balance(pid) == 1000

    def test_multiple_credits_accumulate(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")
        billing_db.credit_coins(pid, 1000, "purchase", idempotency_key="k2")
        assert wallet_balance(pid) == 1500

    def test_balance_equals_ledger_sum_after_credits(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="ka")
        billing_db.credit_coins(pid, 250, "purchase", idempotency_key="kb")

        assert wallet_balance(pid) == ledger_sum(pid)


class TestChargeCoins:
    def test_charge_debits_balance(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")
        new_bal = billing_db.charge_coins(pid, 30, "decompose", generation_ref="gen_1")
        assert new_bal == 470
        assert wallet_balance(pid) == 470

    def test_charge_raises_insufficient_coins(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 10, "purchase", idempotency_key="k1")

        with pytest.raises(InsufficientCoins) as exc_info:
            billing_db.charge_coins(pid, 50, "decompose", generation_ref="gen_2")

        err = exc_info.value
        assert err.balance == 10
        assert err.cost == 50

    def test_charge_does_not_debit_on_insufficient(self):
        """When InsufficientCoins is raised, the balance must not change."""
        pid = make_profile()
        billing_db.credit_coins(pid, 10, "purchase", idempotency_key="k1")

        try:
            billing_db.charge_coins(pid, 50, "decompose", generation_ref="gen_3")
        except InsufficientCoins:
            pass

        assert wallet_balance(pid) == 10

    def test_charge_balance_equals_ledger_sum(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="kx")
        billing_db.charge_coins(pid, 30, "decompose", generation_ref="ref_x")
        billing_db.charge_coins(pid, 5,  "generate",  generation_ref="ref_y")

        assert wallet_balance(pid) == ledger_sum(pid)

    def test_charge_is_idempotent_on_generation_ref(self):
        """Calling charge_coins twice with the same generation_ref charges only once."""
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")

        bal1 = billing_db.charge_coins(pid, 30, "decompose", generation_ref="gen_idem")
        bal2 = billing_db.charge_coins(pid, 30, "decompose", generation_ref="gen_idem")

        assert bal1 == bal2 == 470
        assert wallet_balance(pid) == 470


class TestRefundCoins:
    def test_refund_restores_balance(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")
        billing_db.charge_coins(pid, 30, "decompose", generation_ref="ref_1")
        billing_db.refund_coins(pid, 30, "refund_decompose", generation_ref="ref_1")

        assert wallet_balance(pid) == 500

    def test_refund_is_idempotent_on_generation_ref(self):
        """Calling refund_coins twice with the same ref refunds only once."""
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")
        billing_db.charge_coins(pid, 30, "decompose", generation_ref="ref_2")

        bal1 = billing_db.refund_coins(pid, 30, "refund", generation_ref="ref_2")
        bal2 = billing_db.refund_coins(pid, 30, "refund", generation_ref="ref_2")

        assert bal1 == bal2 == 500
        assert wallet_balance(pid) == 500

    def test_refund_balance_equals_ledger_sum(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 1000, "purchase", idempotency_key="k1")
        billing_db.charge_coins(pid, 40,   "figure",   generation_ref="job_1")
        billing_db.refund_coins(pid, 40,   "refund",   generation_ref="job_1")
        billing_db.charge_coins(pid, 8,    "generate", generation_ref="gen_1")

        assert wallet_balance(pid) == ledger_sum(pid)


class TestRecordStripeEvent:
    def test_first_event_returns_true(self):
        result = billing_db.record_stripe_event("evt_test_001")
        assert result is True

    def test_duplicate_event_returns_false(self):
        billing_db.record_stripe_event("evt_test_002")
        result = billing_db.record_stripe_event("evt_test_002")
        assert result is False

    def test_different_events_are_independent(self):
        r1 = billing_db.record_stripe_event("evt_A")
        r2 = billing_db.record_stripe_event("evt_B")
        assert r1 is True
        assert r2 is True


class TestBalanceInvariant:
    def test_balance_equals_ledger_sum_after_sequence(self):
        """Run a realistic sequence and verify cached balance == SUM(ledger.amount)."""
        pid = make_profile("invariant_user")

        billing_db.credit_coins(pid, 500,  "purchase", idempotency_key="stripe:e1")
        billing_db.credit_coins(pid, 1000, "purchase", idempotency_key="stripe:e2")
        billing_db.charge_coins(pid, 30,   "decompose", generation_ref="d1")
        billing_db.charge_coins(pid, 5,    "generate",  generation_ref="g1")
        billing_db.refund_coins(pid, 5,    "refund",    generation_ref="g1")
        billing_db.charge_coins(pid, 40,   "figure",    generation_ref="f1")
        billing_db.refund_coins(pid, 40,   "refund",    generation_ref="f1")

        cached = wallet_balance(pid)
        derived = ledger_sum(pid)
        assert cached == derived
        assert cached == 1470  # 500+1000-30-5+5-40+40

    def test_balance_never_goes_negative(self):
        """InsufficientCoins prevents negative balance; CHECK constraint is a backstop."""
        pid = make_profile("never_negative")
        billing_db.credit_coins(pid, 10, "purchase", idempotency_key="k1")

        with pytest.raises(InsufficientCoins):
            billing_db.charge_coins(pid, 100, "decompose", generation_ref="r1")

        assert wallet_balance(pid) == 10  # unchanged


class TestGetWallet:
    def test_returns_balance_and_history(self):
        pid = make_profile()
        billing_db.credit_coins(pid, 500, "purchase", idempotency_key="k1")
        billing_db.charge_coins(pid, 30, "decompose", generation_ref="ref1")

        data = billing_db.get_wallet(pid)
        assert data["balance"] == 470
        assert len(data["history"]) == 2
        # Newest first
        assert data["history"][0]["kind"] == "debit"
        assert data["history"][1]["kind"] == "purchase"

    def test_returns_zero_balance_for_fresh_wallet(self):
        pid = make_profile()
        data = billing_db.get_wallet(pid)
        assert data["balance"] == 0
        assert data["history"] == []


class TestConcurrency:
    def test_concurrent_credits_are_serialised(self):
        """Fire multiple credit_coins calls from threads; final balance must be consistent."""
        pid = make_profile("concurrent_user")

        errors = []
        def do_credit(i):
            try:
                billing_db.credit_coins(
                    pid, 10, "purchase",
                    idempotency_key=f"concurrent_key_{i}"
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_credit, args=(i,)) for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert not errors
        data = billing_db.get_wallet(pid)
        assert data["balance"] == 100  # 10 × 10 coins
        assert data["balance"] == ledger_sum(pid)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
