"""Database connection for the Campus Pantry prototype.

Connection settings come from environment variables so no password is stored in code:
    PGHOST (default localhost), PGPORT (5432), PGDATABASE (campus_pantry),
    PGUSER (your login name), PGPASSWORD (asked for if not set and needed).
"""
import getpass
import os
import sys

import psycopg2

SCHEMA = "campus_pantry"


def get_connection():
    host = os.environ.get("PGHOST", "127.0.0.1")
    specified_port = os.environ.get("PGPORT")
    ports_to_try = [int(specified_port)] if specified_port else [5432, 5433]
    dbname = os.environ.get("PGDATABASE", "campus_pantry")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD")

    last_exc = None
    for port in ports_to_try:
        settings = dict(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            options=f"-c search_path={SCHEMA},public",
        )
        if password:
            settings["password"] = password
        try:
            return psycopg2.connect(**settings)
        except psycopg2.OperationalError as exc:
            last_exc = exc
            err_str = str(exc).lower()
            if "password" in err_str and not password and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
                try:
                    settings["password"] = getpass.getpass(f"Password for {settings['user']} on port {port}: ")
                    return psycopg2.connect(**settings)
                except Exception as p_exc:
                    last_exc = p_exc
            continue

    if last_exc:
        raise last_exc
    raise RuntimeError("Could not connect to database on any configured port.")


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
    diag = getattr(exc, "diag", None)
    text = getattr(diag, "message_primary", None) or str(exc).strip().splitlines()[0]
    for constraint, friendly in CONSTRAINT_MESSAGES.items():
        if constraint in text or getattr(diag, "constraint_name", None) == constraint:
            return friendly
    return text
