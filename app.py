import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, make_response
from dotenv import load_dotenv

load_dotenv()

from services.db import (
    get_or_create_user, reset_daily_scans_if_needed, increment_free_scan,
    is_unlocked, unlock_user, save_scan, get_history, log_event,
    save_stripe_session, complete_stripe_session, get_user_by_id, run_migration,
)
from services.ai import analyze_message
from services.stripe_payments import create_checkout_session, verify_session, construct_webhook_event
from services.auth import get_device_id, set_device_cookie

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


# ── Pages ─────────────────────────────────────────────────

@app.route("/")
def index():
    device_id = get_device_id()
    resp = make_response(render_template("index.html"))
    set_device_cookie(resp, device_id)
    return resp


@app.route("/app")
def app_page():
    device_id = get_device_id()
    user = get_or_create_user(device_id)
    unlocked = is_unlocked(user)
    resp = make_response(render_template("app.html", unlocked=unlocked))
    set_device_cookie(resp, device_id)
    return resp


@app.route("/success")
def success_page():
    session_id = request.args.get("session_id")
    return render_template("success.html", session_id=session_id)


@app.route("/cancel")
def cancel_page():
    return render_template("cancel.html")


# ── API: Scan ─────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
def api_scan():
    device_id = get_device_id()
    user = get_or_create_user(device_id)
    user = reset_daily_scans_if_needed(user)
    unlocked = is_unlocked(user)

    data = request.get_json(force=True)
    message_text = data.get("message_text", "").strip()
    direction = data.get("direction", "they")

    if not message_text:
        return jsonify({"error": "Message text is required."}), 400

    # Check entitlement
    if not unlocked and user["free_scans_used_today"] >= 1:
        log_event(user["id"], "paywall_shown")
        return jsonify({"paywall": True}), 402

    # Call AI
    try:
        result = analyze_message(message_text, direction)
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    # Save scan
    result["message_text"] = message_text
    result["direction"] = direction
    scan = save_scan(user["id"], result)

    # Increment free scan counter if not unlocked
    if not unlocked:
        increment_free_scan(user["id"])

    log_event(user["id"], "scan_completed")

    # Build response
    response_data = {
        "id": str(scan["id"]),
        "interest_score": result["interest_score"],
        "red_flag_risk": result["red_flag_risk"],
        "emotional_distance": result["emotional_distance"],
        "ghost_probability": result["ghost_probability"],
        "reply_window": result["reply_window"],
        "confidence": result["confidence"],
        "hidden_signals_count": result["hidden_signals_count"],
        "archetype": result.get("archetype", ""),
        "locked": not unlocked,
    }

    # Summary + archetype always visible (the AI "voice")
    response_data["summary"] = result.get("summary", "")

    # Hidden signals + replies are the paid unlock
    if unlocked:
        response_data["hidden_signals"] = result.get("hidden_signals", [])
        response_data["replies"] = result.get("replies", {})
    else:
        response_data["hidden_signals"] = []
        response_data["replies"] = {}

    resp = make_response(jsonify(response_data))
    set_device_cookie(resp, device_id)
    return resp


# ── API: History ──────────────────────────────────────────

@app.route("/api/history")
def api_history():
    device_id = get_device_id()
    user = get_or_create_user(device_id)
    unlocked = is_unlocked(user)
    scans = get_history(user["id"])

    results = []
    for s in scans:
        item = {
            "id": str(s["id"]),
            "created_at": s["created_at"].isoformat() if s["created_at"] else None,
            "interest_score": s["interest_score"],
            "red_flag_risk": s["red_flag_risk"],
            "emotional_distance": s["emotional_distance"],
            "ghost_probability": s["ghost_probability"],
        }
        if unlocked:
            item["reply_window"] = s["reply_window"]
            item["confidence"] = s["confidence"]
            item["archetype"] = s["archetype"]
            item["summary"] = s["summary"]
        results.append(item)

    # Compute trends if 2+ scans
    trends = {}
    if len(results) >= 2:
        latest = results[0]
        previous = results[1]
        for key in ["interest_score", "ghost_probability"]:
            diff = (latest[key] or 0) - (previous[key] or 0)
            if diff > 5:
                trends[key] = "rising"
            elif diff < -5:
                trends[key] = "falling"
            else:
                trends[key] = "stable"

    resp = make_response(jsonify({"scans": results, "trends": trends, "locked": not unlocked}))
    set_device_cookie(resp, device_id)
    return resp


# ── API: Events ───────────────────────────────────────────

@app.route("/api/event", methods=["POST"])
def api_event():
    device_id = get_device_id()
    user = get_or_create_user(device_id)
    data = request.get_json(force=True)
    event_name = data.get("event_name", "unknown")
    meta = data.get("meta", {})
    log_event(user["id"], event_name, meta)
    return jsonify({"ok": True})


# ── API: Stripe Checkout ─────────────────────────────────

@app.route("/api/create-checkout", methods=["POST"])
def api_create_checkout():
    device_id = get_device_id()
    user = get_or_create_user(device_id)
    data = request.get_json(force=True)
    plan = "monthly"

    if plan != "monthly":
        return jsonify({"error": "Invalid plan"}), 400

    try:
        url, session_id = create_checkout_session(str(user["id"]), plan)
        save_stripe_session(user["id"], session_id, plan)
        log_event(user["id"], f"checkout_clicked_{plan}")
        resp = make_response(jsonify({"url": url}))
        set_device_cookie(resp, device_id)
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Confirm ──────────────────────────────────────────

@app.route("/api/confirm")
def api_confirm():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    result = verify_session(session_id)
    if result:
        unlock_user(result["user_id"], result["plan"])
        complete_stripe_session(session_id)
        log_event(result["user_id"], "purchase_completed", {"plan": result["plan"]})
        return jsonify({"unlocked": True, "plan": result["plan"]})
    return jsonify({"unlocked": False}), 400


# ── Webhook: Stripe ───────────────────────────────────────

@app.route("/webhook/stripe", methods=["POST"])
def webhook_stripe():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")

    try:
        event = construct_webhook_event(payload, sig)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        plan = session.get("metadata", {}).get("plan")
        if user_id and plan:
            unlock_user(user_id, plan)
            complete_stripe_session(session["id"])
            log_event(user_id, "purchase_completed", {"plan": plan, "via": "webhook"})

    return jsonify({"received": True}), 200


# ── CLI: Migrate ──────────────────────────────────────────

@app.cli.command("migrate")
def migrate_cmd():
    run_migration()


# ── Auto-migrate on startup ──────────────────────────────

def auto_migrate():
    """Run migration if tables don't exist yet."""
    try:
        from services.db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='users')")
        exists = cur.fetchone()["exists"]
        conn.close()
        if not exists:
            print("Tables not found, running migration...")
            run_migration()
        else:
            print("Database tables already exist.")
    except Exception as e:
        print(f"Auto-migrate check: {e}")
        # Try running migration anyway
        try:
            run_migration()
        except Exception as e2:
            print(f"Migration failed: {e2}")

auto_migrate()


# ── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
