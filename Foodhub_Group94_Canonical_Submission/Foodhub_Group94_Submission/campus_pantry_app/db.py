"""Database connection for the Campus Pantry university showcase release.

Connection settings come from environment variables so no password is stored in code:
    PGHOST (127.0.0.1), PGPORT (5432), PGDATABASE (campus_pantry),
    PGUSER (postgres), PGPASSWORD (asked for if not set and needed).
Use a dedicated database for this local university showcase.
"""
import getpass
import os
import sys

import psycopg2

SCHEMA = "campus_pantry"


class ConnectionConfigurationError(ValueError):
    """Invalid environment configuration, suitable for a concise startup error."""


def _environment_integer(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except ValueError as exc:
        raise ConnectionConfigurationError(f"{name} must be an integer from {minimum} to {maximum}.") from exc


def get_connection():
    """Connect to exactly the configured endpoint; never guess another port."""
    settings = dict(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=_environment_integer("PGPORT", 5432, 1, 65535),
        dbname=os.environ.get("PGDATABASE", "campus_pantry"),
        user=os.environ.get("PGUSER", "postgres"),
        connect_timeout=_environment_integer("PGCONNECT_TIMEOUT", 5, 1, 60),
        application_name="campus_pantry_cli",
        options=(f"-c search_path={SCHEMA},public -c timezone=Australia/Sydney "
                 "-c statement_timeout=15000 -c lock_timeout=5000 "
                 "-c idle_in_transaction_session_timeout=30000"),
    )
    password = os.environ.get("PGPASSWORD")
    if password is not None:
        settings["password"] = password
    try:
        return psycopg2.connect(**settings)
    except psycopg2.OperationalError as exc:
        interactive = sys.stdin is not None and hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
        if password is None and interactive and "password" in str(exc).lower():
            settings["password"] = getpass.getpass(f"Database password for {settings['user']}: ")
            return psycopg2.connect(**settings)
        raise


# Friendlier wording for constraints a user can trip from the menus.
CONSTRAINT_MESSAGES = {
    "stock_count_counted_qty_check": "A counted quantity cannot be negative.",
    "stock_count_count_type_check": "Count type must be OPENING, CLOSING or SPOT_CHECK.",
    "stock_count_stock_number_fkey": "That stock number does not exist.",
    "stock_count_shift_id_fkey": "That shift does not exist.",
    "booking_session_id_fkey": "That session does not exist.",
    "volunteer_shift_pkey": "A request or assignment already exists for this volunteer and shift.",
    "volunteer_shift_status_check": "Status must be PENDING, APPROVED, or REJECTED.",
    "shift_staff_assignment_pkey": "That staff member is already assigned to this shift.",
    "shift_staff_assignment_shift_id_assignment_role_key": "That duty role is already filled for this shift.",
    "stock_adjustment_quantity_check": "Stock adjustment quantity must be positive.",
    "stock_adjustment_adjustment_kind_check": "Adjustment kind must be RECEIPT or WASTE.",
    "stock_adjustment_shift_id_stock_number_fkey": "No shift stock count record exists for this shift and stock number.",
    "person_unikey_check": "UniKey must be 4 lowercase letters followed by 4 digits (e.g. abcd0123).",
}


def error_message(exc):
    """Return a readable message for a PostgreSQL error (e.g. a trigger's RAISE text)."""
    if isinstance(exc, ConnectionConfigurationError):
        return str(exc)
    diag = getattr(exc, "diag", None)
    pgcode = getattr(exc, "pgcode", None)
    if pgcode in ("22007", "22008"):
        return "Enter a valid date in YYYY-MM-DD format."
    if pgcode in ("40001", "40P01", "55P03"):
        return "Another operation is changing this record. Please retry."
    if pgcode == "57014":
        return "The database operation timed out. Please retry."
    if pgcode == "42P01":
        return "The Campus Pantry schema is missing or incomplete. Run the setup scripts first."
    if isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return "The configured PostgreSQL connection is unavailable; check the server, credentials and connection settings."
    lines = str(exc).strip().splitlines()
    text = getattr(diag, "message_primary", None) or (lines[0] if lines else "The database operation failed.")
    for constraint, friendly in CONSTRAINT_MESSAGES.items():
        if constraint in text or getattr(diag, "constraint_name", None) == constraint:
            return friendly
    return text
