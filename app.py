"""
Tevalovalo Housie90 backend — app.py (v3, cleaned)
- Consolidated & safe CORS
- Optional bearer-token gating for /api/tickets
- SQLite init on import (safe for Render single worker)
- Admin endpoints protected by X-Admin-Key
- GET/POST /validate that marks one-time codes used and issues session token

ENV VARS (Render Dashboard):
- FRONTEND_ORIGIN     -> e.g. https://tevalovalo.netlify.app  (optional; we also allow *.netlify.app)
- DB_FILE             -> optional, defaults to /data/codes.db (or ./codes.db locally)
- REQUIRE_TOKEN_FOR_TICKETS -> "1" / "true" / "yes" to enforce token gating
- ADMIN_KEY           -> required for /admin/* endpoints
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

# === Ticket generator (must exist in your project) ===
from ticket_generator_module import generate_full_strip, validate_strip

app = Flask(__name__)

# ======== Config ========
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").strip()  # exact origin, optional
DEFAULT_DB = "/data/codes.db" if os.path.exists("/data") else "codes.db"
DB_FILE = os.environ.get("DB_FILE", DEFAULT_DB)
REQUIRE_TOKEN_FOR_TICKETS = os.environ.get("REQUIRE_TOKEN_FOR_TICKETS", "").lower() in {"1", "true", "yes"}
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

# Dev-friendly allowlist; FRONTEND_ORIGIN added if set.
ALLOWED_ORIGINS = {
    "http://localhost",
    "http://127.0.0.1",
    "http://127.0.0.1:5500",
    "http://0.0.0.0",
}
if FRONTEND_ORIGIN:
    ALLOWED_ORIGINS.add(FRONTEND_ORIGIN)

# Base CORS; we also do a small manual tweak in after_request for *.netlify.app
CORS(
    app,
    resources={r"/*": {"origins": list(ALLOWED_ORIGINS)}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    """Ensure standard headers; allow any https://*.netlify.app origin dynamically."""
    origin = request.headers.get("Origin", "")
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key")
    resp.headers.setdefault("Vary", "Origin")
    if origin:
        if origin in ALLOWED_ORIGINS or (origin.startswith("https://") and origin.endswith(".netlify.app")):
            resp.headers["Access-Control-Allow-Origin"] = origin
    else:
        resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    return resp

# ======== DB Setup ========
lock = Lock()


def _ensure_db_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def init_db() -> None:
    _ensure_db_dir(DB_FILE)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS codes (
                Code TEXT PRIMARY KEY,
                Used TEXT DEFAULT 'No',
                BuyerName TEXT,
                Expiry TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                Token TEXT PRIMARY KEY,
                Code TEXT,
                Expiry TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_tokens_expiry ON tokens(Expiry)")
        conn.commit()


# Initialize at import time
init_db()

# ======== Health ========
@app.route("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"


@app.route("/whoami")
def whoami():
    return jsonify(
        {
            "service": os.environ.get("RENDER_SERVICE_NAME", "local-or-unknown"),
            "env": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
            "db_file": DB_FILE,
            "require_token_for_tickets": REQUIRE_TOKEN_FOR_TICKETS,
            "frontend_origin": FRONTEND_ORIGIN or "(dev/any in list)",
            "time": iso_utc(utc_now()),
            "allowed_dev_origins": sorted(list(ALLOWED_ORIGINS)),
            "version": "v3",
        }
    )

# ======== Auth helpers ========

def _auth_ok(req) -> bool:
    return bool(ADMIN_KEY) and req.headers.get("X-Admin-Key") == ADMIN_KEY


def _issue_token_for_code(code: str, expiry_iso: str) -> str:
    """Create a session token tied to a code, valid until 'expiry_iso'."""
    tok = uuid.uuid4().hex
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO tokens (Token, Code, Expiry) VALUES (?, ?, ?)",
            (tok, code, expiry_iso),
        )
        conn.commit()
    return tok


def _get_bearer_token(req) -> Optional[str]:
    auth = (req.headers.get("Authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip() or None


def _token_valid(tok: Optional[str]) -> bool:
    if not tok:
        return False
    now = utc_now()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT Expiry FROM tokens WHERE Token = ?", (tok,))
        row = c.fetchone()
        if not row:
            return False
        (expiry_iso,) = row
        exp = parse_iso(expiry_iso)
        return bool(exp and exp > now)


# ======== Validate (one-time) ========
# Accepts GET and POST to avoid 405 and preflight. Marks code used, returns expiry and a token.
@app.route("/validate", methods=["GET", "POST", "OPTIONS"])
def validate():
    if request.method == "OPTIONS":
        return ("", 204)

    if request.method == "GET":
        code = (request.args.get("code") or "").strip()
        buyer = (request.args.get("buyer") or "").strip()
    else:
        data = request.get_json(silent=True) or {}
        code = (data.get("code") or "").strip()
        buyer = (data.get("buyer") or "").strip()

    if not code:
        return jsonify({"valid": False, "reason": "empty_code"}), 400

    with lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT Used, Expiry FROM codes WHERE Code = ?", (code,))
            row = c.fetchone()
            if not row:
                return jsonify({"valid": False, "reason": "not_found"})

            used, expiry = row
            if not expiry:
                expiry = iso_utc(utc_now() + timedelta(days=30))

            # already used?
            if isinstance(used, str) and used.strip().lower() == "yes":
                return jsonify({"valid": False, "reason": "already_used", "expiry": expiry})

            # mark as used (one-time)
            c.execute(
                "UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?",
                (buyer, expiry, code),
            )
            conn.commit()

    token = _issue_token_for_code(code, expiry)
    return jsonify({"valid": True, "reason": "success", "expiry": expiry, "token": token})


# Optional: simple token check endpoint
@app.route("/auth/check", methods=["GET"])
def auth_check():
    tok = _get_bearer_token(request) or (request.args.get("token") or "").strip()
    ok = _token_valid(tok)
    return jsonify({"ok": ok})


# ======== Admin ========
@app.route("/admin/add_code", methods=["POST", "OPTIONS"])
def admin_add_code():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    buyer = (data.get("buyer") or "").strip()
    try:
        days = int(data.get("days") or 30)
    except Exception:
        days = 30

    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400

    expiry = iso_utc(utc_now() + timedelta(days=days))
    with lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO codes (Code, Used, BuyerName, Expiry)
                VALUES (?, 'No', ?, ?)
                """,
                (code, buyer, expiry),
            )
            conn.commit()
    return jsonify({"ok": True, "code": code, "expiry": expiry})


@app.route("/admin/list_codes", methods=["GET"])
def admin_list_codes():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT Code, Used, BuyerName, Expiry FROM codes ORDER BY Code LIMIT 100")
        rows = [
            {"Code": a, "Used": b, "BuyerName": c_, "Expiry": d} for (a, b, c_, d) in c.fetchall()
        ]
    return jsonify({"ok": True, "rows": rows})


# ======== Tickets ========
@app.route("/api/selftest")
def api_selftest():
    try:
        strip = generate_full_strip()
        ok, msg = validate_strip(strip)
        return jsonify({"ok": ok, "msg": msg, "sample_first_ticket": strip[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    # Optional bearer token gating
    if REQUIRE_TOKEN_FOR_TICKETS:
        tok = _get_bearer_token(request)
        if not _token_valid(tok):
            return jsonify({"ok": False, "error": "unauthorized"}), 401

    # cards query param (1..10)
    raw = request.args.get("cards", "1")
    try:
        count = int(raw)
    except Exception:
        count = 1
    count = max(1, min(10, count))

    try:
        all_tickets = []
        for _ in range(count):
            strip = generate_full_strip()  # returns 6 tickets
            all_tickets.extend(strip)
        return jsonify({"ok": True, "cards": all_tickets, "count": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ======== Run (local) ========
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
