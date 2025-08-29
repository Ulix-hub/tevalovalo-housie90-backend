# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os
from threading import Lock
from datetime import datetime, timedelta

app = Flask(__name__)

# ---- CORS (liberal; lock down to your domain later) ----
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Admin-Key"
    return resp

# ---- DB setup ----
DB_FILE = "codes.db"
lock = Lock()

def init_db():
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
        conn.commit()

# Flask 3–safe: run at import time (works on Render/gunicorn)
init_db()

# ---- Fingerprint/health ----
@app.route("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"

@app.route("/whoami")
def whoami():
    return jsonify(
        {
            "service": os.environ.get("RENDER_SERVICE_NAME", "local-or-unknown"),
            "env": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
            "time": datetime.utcnow().isoformat() + "Z",
            "version": "v1",
        }
    )

# ---- Validation (one-time use) ----
# Accepts both GET and POST:
# - GET  /validate?code=CODE001&buyer=Web
# - POST /validate  {"code":"CODE001","buyer":"Web"}
@app.route("/validate", methods=["GET", "POST", "OPTIONS"])
def validate():
    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204)

    # read input
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

            # default expiry if missing
            if not expiry:
                expiry = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

            # already used?
            if isinstance(used, str) and used.lower() == "yes":
                return jsonify({"valid": False, "reason": "already_used", "expiry": expiry})

            # mark as used (one-time)
            c.execute(
                "UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?",
                (buyer, expiry, code),
            )
            conn.commit()

            return jsonify({"valid": True, "reason": "success", "expiry": expiry})

# ---- Admin: add/list codes (protect with a header key) ----
# Set this in Render → Settings → Environment: ADMIN_KEY=UKE202501
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

def _auth_ok(req):
    return bool(ADMIN_KEY) and req.headers.get("X-Admin-Key") == ADMIN_KEY

@app.route("/admin/add_code", methods=["POST", "OPTIONS"])
def admin_add_code():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    buyer = (data.get("buyer") or "").strip()
    days = int(data.get("days") or 30)

    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400

    expiry = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

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
        rows = [{"Code": a, "Used": b, "BuyerName": c_, "Expiry": d} for (a, b, c_, d) in c.fetchall()]
    return jsonify({"ok": True, "rows": rows})

# ---- Tickets ----
# This assumes you already have ticket_generator_module.py with generate_full_strip()
from ticket_generator_module import generate_full_strip

@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    try:
        # 'cards' = number of strips to return (each strip has 6 tickets)
        count = int(request.args.get("cards", 1))
        count = 1 if count < 1 else 10 if count > 10 else count
        all_tickets = []
        for _ in range(count):
            strip = generate_full_strip()  # returns a list of 6 tickets
            all_tickets.extend(strip)
        return jsonify({"cards": all_tickets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- Run (local) ----
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
