# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os, uuid
from threading import Lock
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
from flask_cors import CORS
from flask import request

CORS(
    app,
    resources={r"/*": {"origins": [r"https://.*\.netlify\.app", "http://localhost", "http://127.0.0.1:5500"]}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    origin = request.headers.get("Origin")
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key")
    resp.headers["Vary"] = "Origin"
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
    else:
        resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    return resp


# ======== Config ========
# Frontend origin lock (Step 5). For dev convenience, we also allow localhost/127.0.0.1.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").strip()  # e.g., "https://your-site.netlify.app"

# DB path (Step 4). Defaults to /data/codes.db for Render Disk; falls back to ./codes.db if /data not present.
DEFAULT_DB = "/data/codes.db" if os.path.exists("/data") else "codes.db"
DB_FILE = os.environ.get("DB_FILE", DEFAULT_DB)

# Optional: require Authorization token for /api/tickets (Step 6). Default OFF to avoid breaking your current UI.
REQUIRE_TOKEN_FOR_TICKETS = os.environ.get("REQUIRE_TOKEN_FOR_TICKETS", "").lower() in ("1", "true", "yes")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")  # set this in Render

# ======== CORS ========
# Lock to your production origin if provided, but still allow localhost dev.
cors_origins = ["http://localhost", "http://127.0.0.1:5500", "http://127.0.0.1", "http://0.0.0.0"]
if FRONTEND_ORIGIN:
    cors_origins.append(FRONTEND_ORIGIN)

CORS(
    app,
    resources={r"/*": {"origins": cors_origins}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    # Let flask_cors handle most; ensure standard headers present
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key")
    return resp

# ======== DB Setup ========
lock = Lock()

def _ensure_db_dir(path: str):
    d = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass

def utc_now():
    return datetime.now(timezone.utc)

def iso_utc(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def parse_iso(dt_str: str):
    if not dt_str:
        return None
    try:
        # accept "Z" or offset
        if dt_str.endswith("Z"):
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def init_db():
    _ensure_db_dir(DB_FILE)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Codes table
        c.execute("""
          CREATE TABLE IF NOT EXISTS codes (
            Code TEXT PRIMARY KEY,
            Used TEXT DEFAULT 'No',
            BuyerName TEXT,
            Expiry TEXT
          )
        """)
        # Tokens table (Step 6) — optional gating
        c.execute("""
          CREATE TABLE IF NOT EXISTS tokens (
            Token TEXT PRIMARY KEY,
            Code TEXT,
            Expiry TEXT
          )
        """)
        # Index for faster token expiry lookups
        c.execute("CREATE INDEX IF NOT EXISTS idx_tokens_expiry ON tokens(Expiry)")
        conn.commit()

# Initialize at import time (Flask 3 / gunicorn safe)
init_db()

# ======== Health ========
@app.route("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"

@app.route("/whoami")
def whoami():
    return jsonify({
        "service": os.environ.get("RENDER_SERVICE_NAME", "local-or-unknown"),
        "env": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
        "db_file": DB_FILE,
        "require_token_for_tickets": REQUIRE_TOKEN_FOR_TICKETS,
        "frontend_origin": FRONTEND_ORIGIN or "(dev/any in list)",
        "time": iso_utc(utc_now()),
        "version": "v2"
    })

# ======== Helpers ========
def _auth_ok(req):
    return bool(ADMIN_KEY) and req.headers.get("X-Admin-Key") == ADMIN_KEY

def _issue_token_for_code(code: str, expiry_iso: str) -> str:
    """
    Create a session token tied to a code, valid until 'expiry_iso'.
    (UI can ignore this field; token gating is optional.)
    """
    tok = uuid.uuid4().hex
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO tokens (Token, Code, Expiry) VALUES (?, ?, ?)", (tok, code, expiry_iso))
        conn.commit()
    return tok

def _get_bearer_token(req) -> str | None:
    auth = req.headers.get("Authorization", "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

def _token_valid(tok: str) -> bool:
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

            # default expiry if missing
            if not expiry:
                expiry = iso_utc(utc_now() + timedelta(days=30))

            # already used?
            if isinstance(used, str) and used.lower() == "yes":
                return jsonify({"valid": False, "reason": "already_used", "expiry": expiry})

            # mark as used (one-time)
            c.execute(
                "UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?",
                (buyer, expiry, code),
            )
            conn.commit()

    # issue a token (even if you don't enable gating yet)
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
    days = int(data.get("days") or 30)
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400

    expiry = iso_utc(utc_now() + timedelta(days=days))
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
        rows = [{"Code": a, "Used": b, "BuyerName": c_, "Expiry": d} for (a, b, c_, d) in c.fetchall()]
    return jsonify({"ok": True, "rows": rows})

# ======== Tickets ========
from ticket_generator_module import generate_full_strip  # (and validate_strip only if you added /api/selftest)


@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))
    except Exception:
        count = 1
    count = max(1, min(count, 10))

    all_tickets = []
    for _ in range(count):
        strip = generate_full_strip()   # returns 6 valid tickets (3x9, 15 nums, column ranges, per-column caps)
        all_tickets.extend(strip)
    return jsonify({"cards": all_tickets})


# ======== Run (local) ========
if __name__ == "__main__":
    init_db()
    # For SQLite simplicity, prefer one worker in dev. In Render, set GUNICORN workers via env/Procfile.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
