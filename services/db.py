import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def run_migration():
    """Run the SQL migration file against the database."""
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_init.sql")
    with open(migration_path, "r") as f:
        sql = f.read()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Migration applied successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration error: {e}")
    finally:
        conn.close()


# ── user helpers ──────────────────────────────────────────

def get_or_create_user(device_id: str) -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE device_id = %s", (device_id,))
            user = cur.fetchone()
            if user:
                cur.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (user["id"],))
                conn.commit()
                # refresh
                cur.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
                return dict(cur.fetchone())
            cur.execute(
                "INSERT INTO users (device_id) VALUES (%s) RETURNING *",
                (device_id,),
            )
            conn.commit()
            return dict(cur.fetchone())
    finally:
        conn.close()


def reset_daily_scans_if_needed(user: dict) -> dict:
    """Reset free_scans_used_today if it's a new day."""
    from datetime import date
    today = date.today()
    scan_day = user.get("free_scans_day")
    if scan_day is None or (hasattr(scan_day, 'date') and scan_day != today) or (not hasattr(scan_day, 'date') and scan_day != today):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET free_scans_used_today = 0, free_scans_day = %s WHERE id = %s RETURNING *",
                    (today, user["id"]),
                )
                conn.commit()
                return dict(cur.fetchone())
        finally:
            conn.close()
    return user


def increment_free_scan(user_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET free_scans_used_today = free_scans_used_today + 1 WHERE id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


def is_unlocked(user: dict) -> bool:
    from datetime import datetime
    if user["plan"] == "lifetime":
        return True
    if user["plan"] == "monthly" and user.get("unlocked_until"):
        return user["unlocked_until"] > datetime.utcnow()
    return False


def unlock_user(user_id: str, plan: str):
    from datetime import datetime, timedelta
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if plan == "lifetime":
                cur.execute(
                    "UPDATE users SET plan = 'lifetime', unlocked_until = NULL WHERE id = %s",
                    (user_id,),
                )
            else:
                cur.execute(
                    "UPDATE users SET plan = 'monthly', unlocked_until = %s WHERE id = %s",
                    (datetime.utcnow() + timedelta(days=30), user_id),
                )
        conn.commit()
    finally:
        conn.close()


# ── scan helpers ──────────────────────────────────────────

def save_scan(user_id, data: dict) -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            import json
            cur.execute(
                """INSERT INTO scans
                   (user_id, message_text, direction,
                    interest_score, red_flag_risk, emotional_distance, ghost_probability,
                    reply_window, confidence, hidden_signals_count, hidden_signals,
                    archetype, summary, replies)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (
                    user_id,
                    data["message_text"],
                    data["direction"],
                    data["interest_score"],
                    data["red_flag_risk"],
                    data["emotional_distance"],
                    data["ghost_probability"],
                    data["reply_window"],
                    data["confidence"],
                    data["hidden_signals_count"],
                    json.dumps(data.get("hidden_signals", [])),
                    data.get("archetype", ""),
                    data.get("summary", ""),
                    json.dumps(data.get("replies", {})),
                ),
            )
            conn.commit()
            return dict(cur.fetchone())
    finally:
        conn.close()


def get_history(user_id: str, limit: int = 10) -> list:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scans WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── event helpers ─────────────────────────────────────────

def log_event(user_id, event_name: str, meta: dict = None):
    import json
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO events (user_id, event_name, meta) VALUES (%s, %s, %s)",
                (user_id, event_name, json.dumps(meta or {})),
            )
        conn.commit()
    finally:
        conn.close()


# ── stripe session helpers ────────────────────────────────

def save_stripe_session(user_id, stripe_session_id, plan):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stripe_sessions (user_id, stripe_session_id, plan) VALUES (%s, %s, %s)",
                (user_id, stripe_session_id, plan),
            )
        conn.commit()
    finally:
        conn.close()


def complete_stripe_session(stripe_session_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stripe_sessions SET status='completed' WHERE stripe_session_id=%s RETURNING user_id, plan",
                (stripe_session_id,),
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                return dict(row)
    finally:
        conn.close()
    return None


def get_user_by_id(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()
