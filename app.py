# app.py  (clean, with CORS + /whoami + /validate + /api/tickets)
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os
from threading import Lock
from datetime import datetime, timedelta

app = Flask(__name__)

# ---- CORS ----
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

# ---- DB ----
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

# ---- Health/fingerprint ----
@app.route("/whoami")
def whoami():
    return jsonify({
        "service": os.environ.get("RENDER_SERVICE_NAME", "unknown"),
        "url": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
        "time": datetime.now().isoformat()
    })

@app.route("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"

# ---- Validate (one-time use) ----
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
            if not expiry:
                expiry = (datetime.now() + timedelta(days=30)).isoformat()
            c.execute("UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?",
                      (buyer, expiry, code))
            conn.commit()
    return jsonify({"valid": True, "reason": "success", "expiry": expiry})

# ---- Tickets ----
# Make sure ticket_generator_module.py is in the same repo and exports generate_full_strip()
from ticket_generator_module import generate_full_strip

@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))
    except:
        count = 1
    count = 1 if count < 1 else 10 if count > 10 else count
    all_tickets = []
    for _ in range(count):
        strip = generate_full_strip()  # 6 tickets per strip
        all_tickets.extend(strip)
    return jsonify({"cards": all_tickets})

# ---- Run ----
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
