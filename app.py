# app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import sqlite3, os, re, random, io, uuid
from threading import Lock
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# ------------ Config ------------
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").strip()  # e.g. https://your-site.netlify.app
DEFAULT_DB = "/data/codes.db" if os.path.exists("/data") else "codes.db"
DB_FILE = os.environ.get("DB_FILE", DEFAULT_DB)
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

# Allow Netlify apps + localhost by default (and lock to FRONTEND_ORIGIN if set)
cors_origins = [
    r"https://*.netlify.app",
    "http://localhost",
    "http://127.0.0.1",
    "http://127.0.0.1:5500",
]
if FRONTEND_ORIGIN:
    cors_origins.append(FRONTEND_ORIGIN)

CORS(
    app,
    resources={r"/*": {"origins": cors_origins}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "X-Device-Id"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

@app.after_request
def add_cors_headers(resp):
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key, X-Device-Id")
    return resp

lock = Lock()

# ------------ Time helpers ------------
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
        if dt_str.endswith("Z"):
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

# ------------ Code canonicalization ------------
SECURE_BODY_LEN = 16

def normalize_code(s: str) -> str:
    s = (s or "").strip().upper()
    return re.sub(r"[^A-Z0-9]", "", s)

def to_canonical(code_str: str) -> str:
    """
    Accepts:
      - simple codes like CODE001 (kept as-is)
      - secure display codes like TV-ABCD-EFGH-IJKL-MNOP -> last 16 chars, prefix/dashes ignored
    """
    s = normalize_code(code_str)
    # strip short alpha prefix like "TV" if present
    if len(s) > SECURE_BODY_LEN:
        s = s[-SECURE_BODY_LEN:]
    return s

# ------------ DB setup ------------
def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)) or ".", exist_ok=True)
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
        c.execute("""
          CREATE TABLE IF NOT EXISTS tokens (
            Token TEXT PRIMARY KEY,
            Code TEXT,
            Expiry TEXT
          )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_tokens_expiry ON tokens(Expiry)")
        conn.commit()

init_db()

# ------------ Health ------------
@app.get("/")
def home():
    return "Tevalovalo Housie90 backend is running ✅"

@app.get("/whoami")
def whoami():
    return jsonify({
        "service": os.environ.get("RENDER_SERVICE_NAME", "local-or-unknown"),
        "env": os.environ.get("RENDER_EXTERNAL_URL", "n/a"),
        "db_file": DB_FILE,
        "frontend_origin": FRONTEND_ORIGIN or "(default)",
        "time": iso_utc(utc_now()),
        "version": "v2-balanced"
    })

# ------------ Admin helpers ------------
def _auth_ok(req):
    return bool(ADMIN_KEY) and req.headers.get("X-Admin-Key") == ADMIN_KEY

# ------------ Tokens (optional) ------------
def _issue_token_for_code(code: str, expiry_iso: str) -> str:
    tok = uuid.uuid4().hex
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO tokens (Token, Code, Expiry) VALUES (?, ?, ?)", (tok, code, expiry_iso))
        conn.commit()
    return tok

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

@app.get("/auth/check")
def auth_check():
    tok = (request.headers.get("Authorization", "").replace("Bearer ", "").strip()
           or (request.args.get("token") or "").strip())
    return jsonify({"ok": _token_valid(tok)})

# ------------ Validate (one-time) ------------
@app.route("/validate", methods=["GET", "POST", "OPTIONS"])
def validate():
    if request.method == "OPTIONS":
        return ("", 204)

    if request.method == "GET":
        raw = (request.args.get("code") or "")
        buyer = (request.args.get("buyer") or "").strip()
    else:
        data = request.get_json(silent=True) or {}
        raw = (data.get("code") or "")
        buyer = (data.get("buyer") or "").strip()

    code = to_canonical(raw)
    if not code:
        return jsonify({"valid": False, "reason": "empty_code"}), 400

    with lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        row = c.execute("SELECT Used, Expiry FROM codes WHERE UPPER(Code)=UPPER(?)", (code,)).fetchone()
        if not row:
            return jsonify({"valid": False, "reason": "not_found"}), 404
        used, expiry = row
        if not expiry:
            expiry = iso_utc(utc_now() + timedelta(days=30))
        if isinstance(used, str) and used.lower() == "yes":
            # If you prefer to block reuse entirely, keep this branch as-is.
            # If you want re-validating to succeed (same user), flip to True.
            return jsonify({"valid": False, "reason": "already_used", "expiry": expiry}), 403

        c.execute("UPDATE codes SET Used='Yes', BuyerName=?, Expiry=? WHERE Code=?", (buyer, expiry, code))
        conn.commit()

    token = _issue_token_for_code(code, expiry)
    return jsonify({"valid": True, "reason": "success", "expiry": expiry, "token": token})

# ------------ Admin ------------
@app.post("/admin/add_code")
def admin_add_code():
    if not _auth_ok(request): return jsonify({"ok": False, "error": "unauthorized"}), 403
    data = request.get_json(silent=True) or {}
    raw = (data.get("code") or "")
    code = to_canonical(raw)
    buyer = (data.get("buyer") or "").strip()
    days = int(data.get("days") or 30)
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400
    expiry = iso_utc(utc_now() + timedelta(days=days))
    with lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO codes (Code, Used, BuyerName, Expiry)
            VALUES (?, 'No', ?, ?)
        """, (code, buyer, expiry))
        conn.commit()
    return jsonify({"ok": True, "code": code, "expiry": expiry})

@app.get("/admin/list_codes")
def admin_list_codes():
    if not _auth_ok(request): return jsonify({"ok": False, "error": "unauthorized"}), 403
    limit = int(request.args.get("limit", 200))
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT Code, Used, BuyerName, Expiry FROM codes ORDER BY Code LIMIT ?", (limit,))
        rows = [{"Code": a, "Used": b, "BuyerName": c_, "Expiry": d} for (a, b, c_, d) in c.fetchall()]
    return jsonify({"ok": True, "rows": rows, "count": len(rows)})

@app.post("/admin/bulk_add")
def admin_bulk_add():
    if not _auth_ok(request): return jsonify({"ok": False, "error": "unauthorized"}), 403
    data = request.get_json(silent=True) or {}
    raw_codes = data.get("codes")
    buyer = (data.get("buyer") or "").strip()
    days = int(data.get("days") or 30)

    if not isinstance(raw_codes, list) or not raw_codes:
        return jsonify({"ok": False, "error": "no_codes"}), 400

    expiry = iso_utc(utc_now() + timedelta(days=days))
    added, skipped = [], []

    with lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        for raw in raw_codes:
            try:
                code = to_canonical(raw)
                if not code:
                    skipped.append({"raw": raw, "reason": "empty"})
                    continue
                c.execute("""
                    INSERT OR REPLACE INTO codes (Code, Used, BuyerName, Expiry)
                    VALUES (?, 'No', ?, ?)
                """, (code, buyer, expiry))
                added.append(code)
            except Exception as e:
                skipped.append({"raw": raw, "reason": str(e)})
        conn.commit()

    return jsonify({"ok": True, "added": len(added), "skipped": skipped, "expiry": expiry})

# ------------ Ticket generator (balanced) ------------
def generate_ticket_balanced():
    cols = [
        list(range(1,10)), list(range(10,20)), list(range(20,30)),
        list(range(30,40)), list(range(40,50)), list(range(50,60)),
        list(range(60,70)), list(range(70,80)), list(range(80,91))
    ]
    for c in cols: random.shuffle(c)

    counts = [1]*9
    extras = 15 - sum(counts)
    order = [4,3,5,2,6,1,7,0,8]  # center-out
    i = 0
    while extras > 0:
        ci = order[i % 9]; i += 1
        if counts[ci] < 3:
            counts[ci] += 1
            extras -= 1

    rows = [[0]*9 for _ in range(3)]
    row_used = [0,0,0]
    thirds = [(0,2),(3,5),(6,8)]
    def third_idx(ci): return 0 if ci<=2 else (1 if ci<=5 else 2)
    coverage = [[0,0,0] for _ in range(3)]

    # place 3s
    for ci,cnt in enumerate(counts):
        if cnt == 3:
            for r in range(3):
                rows[r][ci] = 1
                row_used[r] += 1
                coverage[r][third_idx(ci)] = 1

    # place 2s
    for ci,cnt in enumerate(counts):
        if cnt == 2:
            t = third_idx(ci)
            options = sorted(range(3), key=lambda r: (row_used[r], coverage[r][t], random.random()))
            placed = 0
            for r in options:
                if row_used[r] < 5:
                    rows[r][ci] = 1
                    row_used[r] += 1
                    coverage[r][t] = 1
                    placed += 1
                    if placed == 2: break
            if placed < 2:
                for r in range(3):
                    if placed == 2: break
                    if rows[r][ci]==0 and row_used[r] < 5:
                        rows[r][ci] = 1; row_used[r]+=1; coverage[r][t]=1; placed+=1

    # place 1s
    for ci,cnt in enumerate(counts):
        if cnt == 1:
            t = third_idx(ci)
            options = sorted(range(3), key=lambda r: (coverage[r][t], row_used[r], random.random()))
            chosen = None
            for r in options:
                if row_used[r] < 5:
                    chosen = r; break
            if chosen is None:
                caps = [r for r in range(3) if row_used[r] < 5]
                chosen = random.choice(caps) if caps else min(range(3), key=lambda r: row_used[r])
            rows[chosen][ci] = 1; row_used[chosen]+=1; coverage[chosen][t]=1

    # tiny patch: bring any row up to 5
    for r in range(3):
        while row_used[r] < 5:
            donor = max(range(3), key=lambda rr: row_used[rr])
            if row_used[donor] <= 5: break
            movable = [ci for ci in range(9) if rows[donor][ci]==1 and rows[r][ci]==0]
            if not movable: break
            ci = random.choice(movable)
            rows[donor][ci]=0; row_used[donor]-=1
            rows[r][ci]=1; row_used[r]+=1
            coverage = [[0,0,0] for _ in range(3)]
            for rr in range(3):
                for cidx in range(9):
                    if rows[rr][cidx]:
                        coverage[rr][third_idx(cidx)] = 1

    # assign numbers ascending per column
    ticket = [[0]*9 for _ in range(3)]
    for ci in range(9):
        r_idxs = [r for r in range(3) if rows[r][ci]==1]
        need = len(r_idxs)
        nums = sorted([cols[ci].pop() for _ in range(need)])
        r_idxs.sort()
        for k,r in enumerate(r_idxs):
            ticket[r][ci] = nums[k]
    return ticket

def generate_full_strip():
    # 6 balanced tickets make a strip
    return [generate_ticket_balanced() for _ in range(6)]

# optional sanity check
@app.get("/api/selftest")
def api_selftest():
    try:
        strip = generate_full_strip()
        return jsonify({"ok": True, "sample_first_ticket": strip[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/tickets")
def api_tickets():
    try:
        count = int(request.args.get("cards", 1))
    except Exception:
        count = 1
    count = max(1, min(count, 10))
    all_tix = []
    for _ in range(count):
        all_tix.extend(generate_full_strip())  # 6 per strip
    return jsonify({"cards": all_tix})

# ------------ Run ------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
