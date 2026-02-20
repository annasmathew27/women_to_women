from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import math
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret"  # IMPORTANT: change later

DB_NAME = "database.db"


# =========================
# DB helpers
# =========================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # ---- USERS TABLE ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('receiver','provider')),
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cols = {row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()}

    if "location_text" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN location_text TEXT")
    if "lat" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN lat REAL")
    if "lng" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN lng REAL")
    if "service_radius_km" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN service_radius_km REAL")

    # ---- REQUESTS TABLE ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receiver_user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            details TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            FOREIGN KEY(receiver_user_id) REFERENCES users(id)
        )
    """)

    req_cols = {row["name"] for row in cur.execute("PRAGMA table_info(requests)").fetchall()}

    if "location_text" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN location_text TEXT")
    if "lat" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN lat REAL")
    if "lng" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN lng REAL")

    # schedule + wage fields
    if "scheduled_date" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN scheduled_date TEXT")
    if "scheduled_time" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN scheduled_time TEXT")
    if "duration_min" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN duration_min INTEGER")
    if "hourly_wage" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN hourly_wage REAL")

    # serviced tracking
    if "serviced_at" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN serviced_at TEXT")
    if "serviced_by_user_id" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN serviced_by_user_id INTEGER")

    conn.commit()
    conn.close()


# =========================
# Helpers
# =========================
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, role, name, email, location_text, lat, lng, service_radius_km "
        "FROM users WHERE id=?",
        (uid,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Login required"}), 401
                return redirect(url_for("home"))

            if role and user["role"] != role:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Forbidden for this role"}), 403
                return redirect(url_for(f"{user['role']}_dashboard"))

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def find_user_by_email(email):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(role, name, email, password):
    pw_hash = generate_password_hash(password)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (role, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (role, name, email, pw_hash, datetime.utcnow().isoformat()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2) + math.cos(lat1 * p) * math.cos(lat2 * p) * (math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


# =========================
# Pages
# =========================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# =========================
# Receiver auth
# =========================
@app.route("/receiver/signup", methods=["GET", "POST"])
def receiver_signup():
    if request.method == "GET":
        return render_template("receiver_signup.html", error=None)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    gender_declared = (request.form.get("gender_declared") or "").strip().lower()
    confirm_woman = request.form.get("confirm_woman")

    if not name or not email or not password:
        return render_template("receiver_signup.html", error="All fields are required.")

    if gender_declared != "woman":
        return render_template("receiver_signup.html", error="This platform is women-only.")

    if confirm_woman != "yes":
        return render_template("receiver_signup.html", error="You must confirm you are a woman to continue.")

    existing = find_user_by_email(email)
    if existing:
        if existing["role"] == "receiver":
            return render_template("receiver_signup.html", error="Account already exists. Please login instead.")
        return render_template("receiver_signup.html", error="This email is registered as a Provider. Please login as Provider.")

    user_id = create_user("receiver", name, email, password)
    session["user_id"] = user_id
    return redirect(url_for("receiver_dashboard"))


@app.route("/receiver/login", methods=["GET", "POST"])
def receiver_login():
    if request.method == "GET":
        return render_template("receiver_login.html", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = find_user_by_email(email)
    if not user:
        return render_template("receiver_login.html", error="No account found. Please signup.")
    if user["role"] != "receiver":
        return render_template("receiver_login.html", error="This email belongs to a Provider. Please login as Provider.")
    if not check_password_hash(user["password_hash"], password):
        return render_template("receiver_login.html", error="Incorrect password.")

    session["user_id"] = user["id"]
    return redirect(url_for("receiver_dashboard"))


@app.route("/receiver/dashboard")
@login_required(role="receiver")
def receiver_dashboard():
    return render_template("receiver_dashboard.html", user=current_user())


@app.route("/receiver/location", methods=["POST"])
@login_required(role="receiver")
def receiver_location_save():
    user = current_user()
    location_text = (request.form.get("location_text") or "").strip()
    lat_f = to_float(request.form.get("lat"))
    lng_f = to_float(request.form.get("lng"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET location_text=?, lat=?, lng=? WHERE id=?",
        (location_text if location_text else None, lat_f, lng_f, user["id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("receiver_dashboard"))


# =========================
# Provider auth
# =========================
@app.route("/provider/signup", methods=["GET", "POST"])
def provider_signup():
    if request.method == "GET":
        return render_template("provider_signup.html", error=None)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    gender_declared = (request.form.get("gender_declared") or "").strip().lower()
    confirm_woman = request.form.get("confirm_woman")

    if not name or not email or not password:
        return render_template("provider_signup.html", error="All fields are required.")

    if gender_declared != "woman":
        return render_template("provider_signup.html", error="This platform is women-only.")

    if confirm_woman != "yes":
        return render_template("provider_signup.html", error="You must confirm you are a woman to continue.")

    existing = find_user_by_email(email)
    if existing:
        if existing["role"] == "provider":
            return render_template("provider_signup.html", error="Account already exists. Please login instead.")
        return render_template("provider_signup.html", error="This email is registered as a Receiver. Please login as Receiver.")

    user_id = create_user("provider", name, email, password)
    session["user_id"] = user_id
    return redirect(url_for("provider_dashboard"))


@app.route("/provider/login", methods=["GET", "POST"])
def provider_login():
    if request.method == "GET":
        return render_template("provider_login.html", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = find_user_by_email(email)
    if not user:
        return render_template("provider_login.html", error="No account found. Please signup.")
    if user["role"] != "provider":
        return render_template("provider_login.html", error="This email belongs to a Receiver. Please login as Receiver.")
    if not check_password_hash(user["password_hash"], password):
        return render_template("provider_login.html", error="Incorrect password.")

    session["user_id"] = user["id"]
    return redirect(url_for("provider_dashboard"))


@app.route("/provider/dashboard")
@login_required(role="provider")
def provider_dashboard():
    return render_template("provider_dashboard.html", user=current_user())


@app.route("/provider/service", methods=["POST"])
@login_required(role="provider")
def provider_service_save():
    user = current_user()
    lat_f = to_float(request.form.get("lat"))
    lng_f = to_float(request.form.get("lng"))
    radius_f = to_float(request.form.get("service_radius_km"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET lat=?, lng=?, service_radius_km=? WHERE id=?",
        (lat_f, lng_f, radius_f, user["id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("provider_dashboard"))


# =========================
# API: receiver location save + availability check
# =========================
@app.route("/api/receiver/location", methods=["POST"])
@login_required(role="receiver")
def api_receiver_location_save_and_check():
    user = current_user()
    data = request.get_json(silent=True) or {}

    location_text = (data.get("location_text") or "").strip()
    lat_f = to_float(data.get("lat"))
    lng_f = to_float(data.get("lng"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET location_text=?, lat=?, lng=? WHERE id=?",
        (location_text if location_text else None, lat_f, lng_f, user["id"]),
    )
    conn.commit()

    if lat_f is None or lng_f is None:
        conn.close()
        return jsonify({
            "ok": True,
            "can_serve": False,
            "providers_in_range": 0,
            "providers_configured": 0,
            "providers_total": 0,
            "providers_list": [],
            "reason": "No pin set. Click the map or use current location."
        })

    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='provider'")
    providers_total = cur.fetchone()["c"]

    cur.execute("""
        SELECT id, name, lat, lng, service_radius_km
        FROM users
        WHERE role='provider'
          AND lat IS NOT NULL AND lng IS NOT NULL
          AND service_radius_km IS NOT NULL
    """)
    providers = cur.fetchall()
    conn.close()

    providers_configured = len(providers)

    if providers_total == 0:
        return jsonify({
            "ok": True,
            "can_serve": False,
            "providers_in_range": 0,
            "providers_configured": 0,
            "providers_total": 0,
            "providers_list": [],
            "reason": "No providers exist yet. Create a Provider account and set service area."
        })

    if providers_configured == 0:
        return jsonify({
            "ok": True,
            "can_serve": False,
            "providers_in_range": 0,
            "providers_configured": 0,
            "providers_total": providers_total,
            "providers_list": [],
            "reason": "Providers exist, but none have set service pin + radius yet."
        })

    in_range = []
    nearest_any_km = None

    for p in providers:
        p_lat = float(p["lat"])
        p_lng = float(p["lng"])
        p_rad = to_float(p["service_radius_km"])
        if p_rad is None or p_rad <= 0 or p_rad > 200:
            continue

        d = haversine_km(lat_f, lng_f, p_lat, p_lng)
        if nearest_any_km is None or d < nearest_any_km:
            nearest_any_km = d

        if d <= p_rad:
            in_range.append({
                "id": p["id"],
                "name": p["name"],
                "distance_km": round(d, 2),
                "radius_km": p_rad
            })

    in_range.sort(key=lambda x: x["distance_km"])
    providers_in_range = len(in_range)

    if providers_in_range > 0:
        return jsonify({
            "ok": True,
            "can_serve": True,
            "providers_in_range": providers_in_range,
            "providers_configured": providers_configured,
            "providers_total": providers_total,
            "nearest_provider_km": in_range[0]["distance_km"],
            "providers_list": in_range[:5],
            "reason": "Service is available for your location."
        })

    return jsonify({
        "ok": True,
        "can_serve": False,
        "providers_in_range": 0,
        "providers_configured": providers_configured,
        "providers_total": providers_total,
        "nearest_provider_km": round(nearest_any_km, 2) if nearest_any_km is not None else None,
        "providers_list": [],
        "reason": "No providers are in range for this location."
    })


# =========================
# API: requests list (receiver sees own)
# =========================
@app.route("/api/requests", methods=["GET"])
@login_required()
def list_requests():
    user = current_user()
    conn = get_db()
    cur = conn.cursor()

    if user["role"] == "receiver":
        cur.execute("""
            SELECT r.*, u.name AS receiver_name
            FROM requests r
            JOIN users u ON u.id = r.receiver_user_id
            WHERE r.receiver_user_id = ?
            ORDER BY r.id DESC
        """, (user["id"],))
    else:
        cur.execute("""
            SELECT r.*, u.name AS receiver_name
            FROM requests r
            JOIN users u ON u.id = r.receiver_user_id
            ORDER BY r.id DESC
        """)

    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# =========================
# API: receiver creates request
# =========================
@app.route("/api/requests", methods=["POST"])
@login_required(role="receiver")
def create_request():
    user = current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    category = (data.get("category") or "").strip()
    details = (data.get("details") or "").strip()

    scheduled_date = (data.get("scheduled_date") or "").strip() or None
    scheduled_time = (data.get("scheduled_time") or "").strip() or None
    duration_min = to_int(data.get("duration_min"))
    hourly_wage = to_float(data.get("hourly_wage"))

    if not title or not category:
        return jsonify({"error": "title and category are required"}), 400

    if user.get("lat") is None or user.get("lng") is None:
        return jsonify({"error": "Please save your location pin before creating a request."}), 400

    if not scheduled_date or not scheduled_time or not duration_min or hourly_wage is None:
        return jsonify({"error": "Please select date, time, duration, and hourly wage."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO requests
          (receiver_user_id, title, category, details, status, created_at,
           location_text, lat, lng, scheduled_date, scheduled_time, duration_min, hourly_wage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user["id"], title, category, details, "Open", datetime.utcnow().isoformat(),
        user.get("location_text"), user.get("lat"), user.get("lng"),
        scheduled_date, scheduled_time, duration_min, hourly_wage
    ))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"ok": True, "id": new_id}), 201


# =========================
# API: mark serviced (ONLY receiver)
# =========================
@app.route("/api/requests/<int:req_id>/resolve", methods=["POST"])
@login_required(role="receiver")
def mark_serviced(req_id):
    user = current_user()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    r = cur.fetchone()
    if not r:
        conn.close()
        return jsonify({"error": "Request not found"}), 404

    r = dict(r)

    # must be their own request
    if r["receiver_user_id"] != user["id"]:
        conn.close()
        return jsonify({"error": "You can only mark your own request as serviced."}), 403

    # already serviced?
    if (r.get("status") or "").lower() == "serviced":
        conn.close()
        return jsonify({"ok": True, "already": True, "status": "Serviced"}), 200

    now = datetime.utcnow().isoformat()
    cur.execute("""
        UPDATE requests
        SET status='Serviced', serviced_at=?, serviced_by_user_id=?
        WHERE id=?
    """, (now, user["id"], req_id))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "already": False, "status": "Serviced"}), 200


# =========================
# API: provider requests (ONLY in service area)
# - Default: show ONLY Open requests (current)
# - If you want history too: ?history=1
# =========================
@app.route("/api/provider/requests", methods=["GET"])
@login_required(role="provider")
def provider_requests():
    user = current_user()
    p_lat, p_lng = user.get("lat"), user.get("lng")
    radius = user.get("service_radius_km")

    if p_lat is None or p_lng is None or radius is None:
        return jsonify({"error": "Set your service pin + radius"}), 400

    include_history = (request.args.get("history") == "1")

    conn = get_db()
    cur = conn.cursor()

    if include_history:
        cur.execute("""
            SELECT r.*, u.name AS receiver_name
            FROM requests r
            JOIN users u ON u.id = r.receiver_user_id
            ORDER BY r.id DESC
        """)
    else:
        # ✅ current requests ONLY
        cur.execute("""
            SELECT r.*, u.name AS receiver_name
            FROM requests r
            JOIN users u ON u.id = r.receiver_user_id
            WHERE r.status='Open'
            ORDER BY r.id DESC
        """)

    rows = cur.fetchall()
    conn.close()

    out = []
    for row in rows:
        item = dict(row)

        item["distance_km"] = None
        item["can_serve"] = False
        item["serve_reason"] = ""

        r_lat, r_lng = item.get("lat"), item.get("lng")
        if r_lat is None or r_lng is None:
            item["serve_reason"] = "Request has no pin"
            continue

        d = haversine_km(float(p_lat), float(p_lng), float(r_lat), float(r_lng))
        item["distance_km"] = round(d, 2)

        if d <= float(radius):
            item["can_serve"] = True
            item["serve_reason"] = f"Within {radius} km"
            out.append(item)
        else:
            # out-of-range requests are hidden by default
            continue

    return jsonify(out)


# =========================
# Run
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)