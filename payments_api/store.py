from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS checkout_records (
  checkout_reference TEXT PRIMARY KEY,
  session_id TEXT UNIQUE,
  customer_id TEXT,
  subscription_id TEXT,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stripe_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  processed_at TEXT NOT NULL
);
"""


class UnknownCheckoutReference(LookupError):
    """Raised when Stripe refers to a checkout this service did not create."""


@dataclass(frozen=True)
class CheckoutRecord:
    checkout_reference: str
    session_id: str | None
    customer_id: str | None
    subscription_id: str | None
    state: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CheckoutCompletion:
    event_id: str
    event_type: str
    checkout_reference: str
    session_id: str
    customer_id: str
    subscription_id: str


class CheckoutStore:
    def __init__(self, path: str) -> None:
        self._path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.executescript(SCHEMA)
        except sqlite3.OperationalError as error:
            raise OSError(f"Cannot initialize SQLite database: {self._path}") from error

    def create_checkout(self, reference: str) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO checkout_records (
                  checkout_reference, state, created_at, updated_at
                ) VALUES (?, 'creating', ?, ?)
                """,
                (reference, now, now),
            )

    def attach_session(self, reference: str, session_id: str) -> None:
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE checkout_records
                   SET session_id = ?, state = 'pending', updated_at = ?
                 WHERE checkout_reference = ?
                """,
                (session_id, _now(), reference),
            )
            if result.rowcount != 1:
                raise UnknownCheckoutReference(reference)

    def mark_creation_failed(self, reference: str) -> None:
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE checkout_records
                   SET state = 'creation_failed', updated_at = ?
                 WHERE checkout_reference = ?
                """,
                (_now(), reference),
            )
            if result.rowcount != 1:
                raise UnknownCheckoutReference(reference)

    def complete_checkout(self, event: CheckoutCompletion) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                "SELECT 1 FROM stripe_events WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()
            if duplicate is not None:
                connection.commit()
                return False

            result = connection.execute(
                """
                UPDATE checkout_records
                   SET session_id = ?, customer_id = ?, subscription_id = ?,
                       state = 'completed', updated_at = ?
                 WHERE checkout_reference = ?
                """,
                (
                    event.session_id,
                    event.customer_id,
                    event.subscription_id,
                    _now(),
                    event.checkout_reference,
                ),
            )
            if result.rowcount != 1:
                raise UnknownCheckoutReference(event.checkout_reference)

            connection.execute(
                """
                INSERT INTO stripe_events (event_id, event_type, processed_at)
                VALUES (?, ?, ?)
                """,
                (event.event_id, event.event_type, _now()),
            )
            connection.commit()
            return True

    def get_checkout(self, reference: str) -> CheckoutRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT checkout_reference, session_id, customer_id,
                       subscription_id, state, created_at, updated_at
                  FROM checkout_records
                 WHERE checkout_reference = ?
                """,
                (reference,),
            ).fetchone()
        return CheckoutRecord(**dict(row)) if row is not None else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
