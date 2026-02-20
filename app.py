from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import math
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret"  # IMPORTANT: change later

DB_NAME = "database.db"

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

    # Add missing columns to users (safe)
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

    # Add missing columns to requests (safe)
    req_cols = {row["name"] for row in cur.execute("PRAGMA table_info(requests)").fetchall()}

    if "location_text" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN location_text TEXT")
    if "lat" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN lat REAL")
    if "lng" not in req_cols:
        cur.execute("ALTER TABLE requests ADD COLUMN lng REAL")

    conn.commit()
    conn.close()


# --------- helpers ----------
def current_user():
    
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, role, name, email, location_text, lat, lng, service_radius_km FROM users WHERE id=?", (uid,))

    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None



def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()

            # If not logged in:
            if not user:
                # ✅ If API call, return JSON, not redirect HTML
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Login required"}), 401
                return redirect(url_for("home"))

            # If wrong role:
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
        (role, name, email, pw_hash, datetime.utcnow().isoformat())
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
    a = (math.sin(dlat/2)**2) + math.cos(lat1*p)*math.cos(lat2*p)*(math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --------- routes ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ---- Receiver Auth ----
@app.route("/receiver/signup", methods=["GET", "POST"])
def receiver_signup():
    if request.method == "GET":
        return render_template("receiver_signup.html", error=None)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not name or not email or not password:
        return render_template("receiver_signup.html", error="All fields are required.")

    existing = find_user_by_email(email)
    if existing:
        # if exists, ask them to login (and show correct link based on role)
        role = existing["role"]
        if role == "receiver":
            return render_template("receiver_signup.html", error="Account already exists. Please login instead.")
        else:
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
    user = current_user()
    return render_template("receiver_dashboard.html", user=user)
@app.route("/receiver/location", methods=["POST"])
@login_required(role="receiver")
def receiver_location_save():
    user = current_user()

    location_text = (request.form.get("location_text") or "").strip()
    lat = request.form.get("lat")
    lng = request.form.get("lng")

    # Convert lat/lng safely
    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    lat_f = to_float(lat)
    lng_f = to_float(lng)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET location_text=?, lat=?, lng=? WHERE id=?",
        (location_text if location_text else None, lat_f, lng_f, user["id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("receiver_dashboard"))


# ---- Provider Auth ----
@app.route("/provider/signup", methods=["GET", "POST"])
def provider_signup():
    if request.method == "GET":
        return render_template("provider_signup.html", error=None)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not name or not email or not password:
        return render_template("provider_signup.html", error="All fields are required.")

    existing = find_user_by_email(email)
    if existing:
        role = existing["role"]
        if role == "provider":
            return render_template("provider_signup.html", error="Account already exists. Please login instead.")
        else:
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
    user = current_user()
    return render_template("provider_dashboard.html", user=user)

# ---- (Optional) API for receiver to create request ----
@app.route("/api/requests", methods=["GET"])
def list_requests():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, u.name AS receiver_name
        FROM requests r
        JOIN users u ON u.id = r.receiver_user_id
        ORDER BY r.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
@app.route("/api/requests/<int:req_id>/resolve", methods=["POST"])
def resolve_request(req_id):
    # optionally enforce provider only:
    user = current_user()
    if not user or user["role"] != "provider":
        return jsonify({"error": "Provider login required"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE requests SET status='Resolved' WHERE id=?", (req_id,))
    conn.commit()
    updated = cur.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "Request not found"}), 404
    return jsonify({"ok": True})
@app.route("/provider/service", methods=["POST"])
@login_required(role="provider")
def provider_service_save():
    user = current_user()

    lat = request.form.get("lat")
    lng = request.form.get("lng")
    radius = request.form.get("service_radius_km")

    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    lat_f = to_float(lat)
    lng_f = to_float(lng)
    radius_f = to_float(radius)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET lat=?, lng=?, service_radius_km=? WHERE id=?",
        (lat_f, lng_f, radius_f, user["id"])
    )
    conn.commit()
    conn.close()
    return redirect(url_for("provider_dashboard"))




@app.route("/api/provider/requests", methods=["GET"])
@login_required(role="provider")
def provider_requests():
    user = current_user()
    p_lat, p_lng = user.get("lat"), user.get("lng")
    radius = user.get("service_radius_km")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, u.name AS receiver_name
        FROM requests r
        JOIN users u ON u.id = r.receiver_user_id
        ORDER BY r.id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        item = dict(r)

        # default statuses
        item["distance_km"] = None
        item["can_serve"] = None
        item["serve_reason"] = ""

        r_lat, r_lng = item.get("lat"), item.get("lng")

        if r_lat is None or r_lng is None:
            item["can_serve"] = False
            item["serve_reason"] = "No pin for request"
        elif p_lat is None or p_lng is None or radius is None:
            item["can_serve"] = False
            item["serve_reason"] = "Set your service pin + radius"
        else:
            d = haversine_km(float(p_lat), float(p_lng), float(r_lat), float(r_lng))
            item["distance_km"] = round(d, 2)
            if d <= float(radius):
                item["can_serve"] = True
                item["serve_reason"] = f"Within {radius} km"
            else:
                item["can_serve"] = False
                item["serve_reason"] = f"Out of range ({radius} km)"

        out.append(item)

    return jsonify(out)
@app.route("/api/receiver/location", methods=["POST"])
@login_required(role="receiver")
def api_receiver_location_save_and_check():
    user = current_user()
    data = request.get_json(silent=True) or {}

    location_text = (data.get("location_text") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")

    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    lat_f = to_float(lat)
    lng_f = to_float(lng)

    # 1) Save receiver location
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET location_text=?, lat=?, lng=? WHERE id=?",
        (location_text if location_text else None, lat_f, lng_f, user["id"])
    )
    conn.commit()

    # If receiver has no pin, return immediately
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

    # 2) Count total provider accounts (info only)
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='provider'")
    providers_total = cur.fetchone()["c"]

    # 3) Fetch only CONFIGURED providers (pin + radius)
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

    # Clear reasons for special cases
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

    # 4) Compute in-range providers + debug list
    in_range = []
    nearest_any_km = None

    for p in providers:
        p_lat = float(p["lat"])
        p_lng = float(p["lng"])

        try:
            p_rad = float(p["service_radius_km"])
        except (TypeError, ValueError):
            continue

        # ✅ radius validation (avoid wrong counts)
        # Change cap if you want bigger service areas
        if p_rad <= 0 or p_rad > 200:
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
            "providers_list": in_range[:5],  # ✅ top 5 for debugging/UI
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

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
