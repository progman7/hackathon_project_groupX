"""
SpotUM - UM Study Spot Finder
Shows which study rooms are free/busy in real time, lets logged-in students
book rooms, and provides a simple admin panel to manage rooms and bookings.

Room data is seeded from Maastricht University's official facility overview
("Room booking at Maastricht University" PDF, Servicepoint Facility Services).
Note: UM does not expose a public live-occupancy API, so this seed list reflects
real room/building names and capacities, but real-time free/busy status is driven
by bookings made through this app (an MVP layer on top of UM's actual room stock).
"""
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "spotum2026")

DB_PATH = os.path.join(os.path.dirname(__file__), "rooms.db")

UM_ROOMS = [
    ("Tutorial Room B0.113", "Law - Bouillonstraat 1-3", 30),
    ("Tutorial Room B0.115", "Law - Bouillonstraat 1-3", 30),
    ("Tutorial Room B0.118", "Law - Bouillonstraat 1-3", 30),
    ("Tutorial Room C1.306", "Law - Bouillonstraat 1-3", 30),
    ("Statenzaal (Lecture Hall)", "Law - Bouillonstraat 1-3", 120),
    ("Feestzaal (Lecture Hall)", "Law - Bouillonstraat 1-3", 80),
    ("Tutorial Room GG76-1", "FASoS - GG76", 16),
    ("Tutorial Room GG76-2", "FASoS - GG76", 16),
    ("Tutorial Room GG76-3", "FASoS - GG76", 30),
    ("Tutorial Room GG80-1", "FASoS - GG80-82", 16),
    ("Tutorial Room GG82-1", "FASoS - GG80-82", 16),
    ("Turnzaal A.0 (Lecture Hall)", "FASoS - GG90-92", 150),
    ("Tutorial Room UNS40-101", "FHML/FPN - UNS40", 12),
    ("Tutorial Room UNS40-102", "FHML/FPN - UNS40", 14),
    ("Tutorial Room UNS40-103", "FHML/FPN - UNS40", 16),
    ("Tutorial Room UNS60-201", "FHML - UNS60", 12),
    ("Tutorial Room UNS60-202", "FHML - UNS60", 20),
    ("Lecture Hall B.0647", "FHML/FPN - UNS40", 400),
    ("Lecture Hall B0.673", "FHML/FPN - UNS40", 150),
    ("Lecture Hall A0.771", "FHML/FPN - UNS40", 70),
    ("Tutorial Room OXF55-1", "FPN - OXF55", 14),
    ("Jo Ritzenzaal (Auditorium)", "FPN - OXF55", 200),
    ("Lecture Hall S0.007", "FPN - OXF55", 69),
    ("Study Room Zwingelput-1", "UCM - Zwingelput 4", 12),
    ("Study Room Zwingelput-2", "UCM - Zwingelput 4", 20),
    ("Study Room Zwingelput-3", "UCM - Zwingelput 4", 40),
    ("Lecture Hall B0.014", "UCM - Zwingelput 4", 90),
    ("Tutorial Room DKE-1", "DKE - Bouillonstraat 8-10", 12),
    ("Tutorial Room DKE-2", "DKE - Bouillonstraat 8-10", 20),
    ("Lecture Hall 0.015", "DKE - Bouillonstraat 8-10", 48),
    ("Study Association Room SBE-1", "SBE - Tongersestraat 53", 20),
    ("Lecture Hall A1.01", "SBE - Tongersestraat 53", 500),
    ("Aula H0.01", "SBE - Tongersestraat 53", 173),
    ("Study Room UB Randwyck-1", "University Library - Randwyck", 12),
    ("Study Room UB Randwyck-2", "University Library - Randwyck", 20),
    ("Study Room UB Randwyck-3", "University Library - Randwyck", 46),
    ("Study Room UB Inner City-1", "University Library - Inner City", 12),
    ("Study Room UB Inner City-2", "University Library - Inner City", 20),
    ("Study Room UB Inner City-3", "University Library - Inner City", 30),
    ("Visitors Centre Study Area", "SSC - Bonnefantenstraat 2", 15),
    ("Karl-Dittrich Zaal", "SSC - Bonnefantenstraat 2", 69),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            building TEXT NOT NULL,
            capacity INTEGER DEFAULT 4
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            booked_by TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    c.execute("SELECT COUNT(*) FROM rooms")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO rooms (name, building, capacity) VALUES (?, ?, ?)", UM_ROOMS)
    conn.commit()
    conn.close()


def get_room_status():
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    c.execute("SELECT id, name, building, capacity FROM rooms")
    rooms = c.fetchall()

    result = []
    for room in rooms:
        c.execute("""
            SELECT id, start_time, end_time, booked_by, user_id FROM bookings
            WHERE room_id = ? AND start_time <= ? AND end_time >= ?
        """, (room["id"], now, now))
        booking = c.fetchone()
        status = "busy" if booking else "free"

        c.execute("""
            SELECT id, start_time, end_time, booked_by, user_id FROM bookings
            WHERE room_id = ? AND end_time >= ?
            ORDER BY start_time ASC
        """, (room["id"], now))
        upcoming = [dict(row) for row in c.fetchall()]

        result.append({
            "id": room["id"],
            "name": room["name"],
            "building": room["building"],
            "capacity": room["capacity"],
            "status": status,
            "until": booking["end_time"] if booking else None,
            "bookings": upcoming
        })
    conn.close()
    return result


# ---------- Student auth helpers ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def api_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "You must be logged in to do this"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------- Public / homepage ----------

@app.route("/")
def home():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM rooms")
    total_rooms = c.fetchone()[0]
    conn.close()
    return render_template("home.html", total_rooms=total_rooms)


@app.route("/app")
@login_required
def app_page():
    return render_template("index.html", user_name=session.get("user_name"))


# ---------- Student auth routes ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "Please fill in all fields."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            if c.fetchone():
                error = "An account with this email already exists."
            else:
                password_hash = generate_password_hash(password)
                c.execute(
                    "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (name, email, password_hash, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                user_id = c.lastrowid
                conn.close()
                session["user_id"] = user_id
                session["user_name"] = name
                return redirect(url_for("app_page"))
            conn.close()
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, name, password_hash FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            next_url = request.args.get("next") or url_for("app_page")
            return redirect(next_url)
        error = "Incorrect email or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect(url_for("home"))


# ---------- Student profile ----------

@app.route("/profile")
@login_required
def profile():
    conn = get_conn()
    c = conn.cursor()
    user_id = session["user_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    c.execute("""
        SELECT bookings.id, bookings.start_time, bookings.end_time,
               rooms.name as room_name, rooms.building as room_building
        FROM bookings JOIN rooms ON bookings.room_id = rooms.id
        WHERE bookings.user_id = ? AND bookings.end_time >= ?
        ORDER BY bookings.start_time ASC
    """, (user_id, now))
    upcoming = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT bookings.id, bookings.start_time, bookings.end_time,
               rooms.name as room_name, rooms.building as room_building
        FROM bookings JOIN rooms ON bookings.room_id = rooms.id
        WHERE bookings.user_id = ? AND bookings.end_time < ?
        ORDER BY bookings.start_time DESC
        LIMIT 30
    """, (user_id, now))
    past = [dict(r) for r in c.fetchall()]
    conn.close()

    return render_template(
        "profile.html",
        user_name=session.get("user_name"),
        upcoming=upcoming,
        past=past
    )


# ---------- Room / booking API (requires student login) ----------

@app.route("/api/rooms")
@api_login_required
def api_rooms():
    return jsonify(get_room_status())


@app.route("/api/book", methods=["POST"])
@api_login_required
def api_book():
    data = request.get_json()
    room_id = data.get("room_id")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    user_id = session["user_id"]
    booked_by = session.get("user_name", "Student")

    if not all([room_id, start_time, end_time]):
        return jsonify({"error": "Missing required fields"}), 400

    if start_time >= end_time:
        return jsonify({"error": "End time must be after start time"}), 400

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id FROM bookings
        WHERE room_id = ? AND start_time < ? AND end_time > ?
    """, (room_id, end_time, start_time))
    conflict = c.fetchone()

    if conflict:
        conn.close()
        return jsonify({"error": "This time slot overlaps with an existing booking"}), 409

    c.execute("""
        INSERT INTO bookings (room_id, user_id, booked_by, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    """, (room_id, user_id, booked_by, start_time, end_time))
    conn.commit()
    booking_id = c.lastrowid
    conn.close()

    return jsonify({"success": True, "booking_id": booking_id}), 201


@app.route("/api/cancel/<int:booking_id>", methods=["DELETE"])
@api_login_required
def api_cancel(booking_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM bookings WHERE id = ?", (booking_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Booking not found"}), 404
    if row["user_id"] != session["user_id"] and not session.get("is_admin"):
        conn.close()
        return jsonify({"error": "You can only cancel your own bookings"}), 403

    c.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ---------- Admin auth ----------

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect password"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ---------- Admin dashboard ----------

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM rooms ORDER BY building, name")
    rooms = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT bookings.id, bookings.booked_by, bookings.start_time, bookings.end_time,
               rooms.name as room_name, rooms.building as room_building
        FROM bookings JOIN rooms ON bookings.room_id = rooms.id
        ORDER BY bookings.start_time DESC
        LIMIT 50
    """)
    bookings = [dict(b) for b in c.fetchall()]

    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    conn.close()

    return render_template("admin_dashboard.html", rooms=rooms, bookings=bookings, user_count=user_count)


@app.route("/admin/rooms/add", methods=["POST"])
@admin_required
def admin_add_room():
    name = request.form.get("name", "").strip()
    building = request.form.get("building", "").strip()
    capacity = request.form.get("capacity", "4").strip() or "4"

    if name and building:
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO rooms (name, building, capacity) VALUES (?, ?, ?)",
                   (name, building, int(capacity)))
        conn.commit()
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/rooms/delete/<int:room_id>", methods=["POST"])
@admin_required
def admin_delete_room(room_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM bookings WHERE room_id = ?", (room_id,))
    c.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/bookings/delete/<int:booking_id>", methods=["POST"])
@admin_required
def admin_delete_booking(booking_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
