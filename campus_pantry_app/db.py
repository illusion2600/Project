"""Database connection for the Campus Pantry prototype.

Connection settings come from environment variables so no password is stored in code:
    PGHOST (default localhost), PGPORT (5432), PGDATABASE (campus_pantry),
    PGUSER (your login name), PGPASSWORD (asked for if not set and needed).
"""
import getpass
import os

import psycopg2

SCHEMA = "campus_pantry"


def get_connection():
    settings = dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "campus_pantry"),
        user=os.environ.get("PGUSER", getpass.getuser()),
        # Every query in the app runs inside the campus_pantry schema.
        options=f"-c search_path={SCHEMA},public",
    )
    password = os.environ.get("PGPASSWORD")
    if password:
        settings["password"] = password
    try:
        return psycopg2.connect(**settings)
    except psycopg2.OperationalError as exc:
        if "password" not in str(exc).lower() or password:
            raise
        settings["password"] = getpass.getpass(f"Password for {settings['user']}: ")
        return psycopg2.connect(**settings)


# Friendlier wording for constraints a user can trip from the menus.
CONSTRAINT_MESSAGES = {
    "stock_count_counted_qty_check": "A counted quantity cannot be negative.",
    "stock_count_count_type_check": "Count type must be OPENING, CLOSING or SPOT_CHECK.",
    "stock_count_stock_number_fkey": "That stock number does not exist.",
    "stock_count_shift_id_fkey": "That shift does not exist.",
    "booking_session_id_fkey": "That session does not exist.",
}


def error_message(exc):
    """Return a readable message for a PostgreSQL error (e.g. a trigger's RAISE text)."""
    diag = getattr(exc, "diag", None)
    text = getattr(diag, "message_primary", None) or str(exc).strip().splitlines()[0]
    for constraint, friendly in CONSTRAINT_MESSAGES.items():
        if constraint in text or getattr(diag, "constraint_name", None) == constraint:
            return friendly
    return text
