"""Concurrency demo: the same student books two different sessions at the same moment.

Run:  python concurrency_demo.py SESSION_A SESSION_B
(two future sessions on the same day; the script uses student shre2225 and cancels its
own test bookings at the end, so the sample data is left as it was).

Round 1 — WITHOUT the student lock: both transactions check "no booking today yet"
before either commits, so BOTH bookings succeed and the one-per-day rule is broken.
Round 2 — WITH the student lock (what services.book_session does): the second
transaction waits for the first to commit, then sees its booking and is rejected.
"""
import os
import secrets
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2

from db import error_message, get_connection

STUDENT = "alex1001"


def attempt(label, session_id, use_lock, hold_seconds, results):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                if use_lock:
                    cur.execute("SELECT unikey FROM student WHERE unikey = %s FOR UPDATE", (STUDENT,))
                cur.execute("""
                    INSERT INTO booking (student_unikey, session_id, qr_token)
                    VALUES (%s, %s, %s) RETURNING booking_id""",
                    (STUDENT, session_id, "DEMO-" + secrets.token_hex(6)))
                booking_id = cur.fetchone()[0]
                time.sleep(hold_seconds)          # keep the transaction open
        results[label] = f"booked (booking {booking_id})"
    except psycopg2.Error as exc:
        results[label] = f"rejected: {error_message(exc)}"
    finally:
        conn.close()


def clean_up():
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE booking SET status = 'CANCELLED'
                WHERE student_unikey = %s AND qr_token LIKE 'DEMO-%%' AND status = 'CONFIRMED'""",
                (STUDENT,))
    conn.close()


def run_round(title, use_lock, session_a, session_b):
    results = {}
    first = threading.Thread(target=attempt, args=("request 1", session_a, use_lock, 2, results))
    second = threading.Thread(target=attempt, args=("request 2", session_b, use_lock, 0, results))
    first.start()
    time.sleep(0.5)                               # request 2 arrives while 1 is still open
    second.start()
    first.join()
    second.join()
    print(f"\n{title}")
    for label in ("request 1", "request 2"):
        print(f"  {label}: {results[label]}")
    clean_up()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python concurrency_demo.py SESSION_A SESSION_B")
    a, b = int(sys.argv[1]), int(sys.argv[2])
    clean_up()
    run_round("Round 1 — no student lock:", False, a, b)
    run_round("Round 2 — student row locked first:", True, a, b)

