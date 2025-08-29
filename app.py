from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os
from threading import Lock
from datetime import datetime, timedelta

app = Flask(__name__)

# ---- CORS (liberal; you can restrict to your Netlify domain later) ----
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp

# ---- DB setup ----
DB_FILE = "codes.db"
lock = Lock()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
          CREATE TABLE IF NOT EXISTS codes (
            Code TEXT PRIMARY KEY,
            Used TEXT DEFAULT 'No',
            BuyerName TEXT,
            Expiry TEXT
          )
        """)
        conn.commit()
# ensure the table exists even on Render (gunicorn import)
init_db()

@app.before_first_request
def _ensure_db_on_first_request():
    init_db()

# ---- Fingerprint/health ----
@app.route("/whoami")
def whoami():
    return jsonify({
        "service": os.environ.get("RENDER_SERVICE_NAME", "local-or-unknown"),
        "env": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
        "time": datetime.now().isoformat()
    })

@app.route("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"

# ---- Validation (one-time use) ----
@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json() or {}
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
            if used.lower() == "yes":
                return jsonify({"valid": False, "reason": "already_used"})
            # if no expiry set, default to +30 days
            if not expiry:
                expiry = (datetime.now() + timedelta(days=30)).isoformat()
            # mark used
            c.execute("UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?",
                      (buyer, expiry, code))
            conn.commit()
            return jsonify({"valid": True, "reason": "success", "expiry": expiry})

# ---- Admin: add/list codes (protect with a header key) ----
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

def _auth_ok(req):
    return ADMIN_KEY and req.headers.get("X-Admin-Key") == ADMIN_KEY

@app.route("/admin/add_code", methods=["POST"])
def admin_add_code():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    data = request.get_json() or {}
    code = (data.get("code") or "").strip()
    buyer = (data.get("buyer") or "").strip()
    days = int(data.get("days") or 30)
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    with lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO codes (Code, Used, BuyerName, Expiry)
                VALUES (?, 'No', ?, ?)
            """, (code, buyer, expiry))
            conn.commit()
    return jsonify({"ok": True, "code": code, "expiry": expiry})

@app.route("/admin/list_codes", methods=["GET"])
def admin_list_codes():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT Code, Used, BuyerName, Expiry FROM codes ORDER BY Code LIMIT 100")
        rows = [{"Code": a, "Used": b, "BuyerName": d, "Expiry": e} for (a,b,d,e) in c.fetchall()]
    return jsonify({"ok": True, "rows": rows})

# ---- Tickets ----
from ticket_generator_module import generate_full_strip  # your existing module

@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))
        count = 1 if count < 1 else 10 if count > 10 else count
        all_tickets = []
        for _ in range(count):
            strip = generate_full_strip()  # 6 tickets per strip
            all_tickets.extend(strip)
        return jsonify({"cards": all_tickets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- Run ----
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
