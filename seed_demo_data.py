"""
Seed SpotUM with demo students and a realistic, non-duplicated set of bookings.
Only 11-15 unique rooms get booked (by different students, at different times),
out of the full room list -- so the rest stay visibly "Free".

Usage:
    python seed_demo_data.py
"""
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import sqlite3
import random

from app import init_db, DB_PATH

random.seed(42)  # reproducible demo data

DEMO_STUDENTS = [
    ("Sofia Bakker", "sofia.bakker@student.maastrichtuniversity.nl", "password123"),
    ("Liam de Vries", "liam.devries@student.maastrichtuniversity.nl", "password123"),
    ("Anna Schmidt", "anna.schmidt@student.maastrichtuniversity.nl", "password123"),
    ("Marco Rossi", "marco.rossi@student.maastrichtuniversity.nl", "password123"),
    ("Ilias Petrov", "ilias.petrov@student.maastrichtuniversity.nl", "password123"),
    ("Emma Janssen", "emma.janssen@student.maastrichtuniversity.nl", "password123"),
    ("Noah Peeters", "noah.peeters@student.maastrichtuniversity.nl", "password123"),
    ("Laura Wagner", "laura.wagner@student.maastrichtuniversity.nl", "password123"),
    ("Thomas Müller", "thomas.muller@student.maastrichtuniversity.nl", "password123"),
    ("Zoe van Dijk", "zoe.vandijk@student.maastrichtuniversity.nl", "password123"),
    ("Diego Fernandez", "diego.fernandez@student.maastrichtuniversity.nl", "password123"),
    ("Mia Kowalski", "mia.kowalski@student.maastrichtuniversity.nl", "password123"),
    ("Lucas Meijer", "lucas.meijer@student.maastrichtuniversity.nl", "password123"),
    ("Eva Smit", "eva.smit@student.maastrichtuniversity.nl", "password123"),
    ("Julian Becker", "julian.becker@student.maastrichtuniversity.nl", "password123"),
    ("Nina Visser", "nina.visser@student.maastrichtuniversity.nl", "password123"),
    ("David Novak", "david.novak@student.maastrichtuniversity.nl", "password123"),
    ("Sara Martins", "sara.martins@student.maastrichtuniversity.nl", "password123"),
    ("Oliver Braun", "oliver.braun@student.maastrichtuniversity.nl", "password123"),
    ("Chloe Peters", "chloe.peters@student.maastrichtuniversity.nl", "password123"),
    ("Mateo Silva", "mateo.silva@student.maastrichtuniversity.nl", "password123"),
    ("Julia van Leeuwen", "julia.vanleeuwen@student.maastrichtuniversity.nl", "password123"),
    ("Daniel Horvath", "daniel.horvath@student.maastrichtuniversity.nl", "password123"),
    ("Isabella Rossi", "isabella.rossi@student.maastrichtuniversity.nl", "password123"),
    ("Finn O'Brien", "finn.obrien@student.maastrichtuniversity.nl", "password123"),
    ("Lena Hoffmann", "lena.hoffmann@student.maastrichtuniversity.nl", "password123"),
    ("Rafael Costa", "rafael.costa@student.maastrichtuniversity.nl", "password123"),
    ("Amelie Dubois", "amelie.dubois@student.maastrichtuniversity.nl", "password123"),
    ("Kacper Nowak", "kacper.nowak@student.maastrichtuniversity.nl", "password123"),
    ("Freya Andersen", "freya.andersen@student.maastrichtuniversity.nl", "password123"),
    ("Mohammed Al-Sayed", "mohammed.alsayed@student.maastrichtuniversity.nl", "password123"),
    ("Valentina Popescu", "valentina.popescu@student.maastrichtuniversity.nl", "password123"),
    ("Erik Johansson", "erik.johansson@student.maastrichtuniversity.nl", "password123"),
]

# Time slots to spread bookings across (hour, minute, duration_min, day_offset)
# Mix of currently-ongoing, later today, tomorrow, and day after.
TIME_SLOTS = [
    ("now", -30, 90),      # ongoing right now
    ("now", -10, 45),      # ongoing right now
    (0, 8, 30, 60),
    (0, 9, 30, 90),
    (0, 11, 0, 60),
    (0, 12, 30, 90),
    (0, 14, 0, 60),
    (0, 15, 30, 120),
    (0, 17, 0, 60),
    (0, 18, 30, 90),
    (0, 20, 0, 60),
    (0, 21, 30, 90),
    (1, 9, 0, 60),
    (1, 13, 0, 90),
    (1, 17, 0, 60),
]


def seed():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Ensure all demo students exist
    user_ids = []
    for name, email, password in DEMO_STUDENTS:
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing = c.fetchone()
        if existing:
            user_ids.append((existing["id"], name))
            continue
        password_hash = generate_password_hash(password)
        c.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        user_ids.append((c.lastrowid, name))
    conn.commit()

    c.execute("SELECT id, name FROM rooms")
    rooms = c.fetchall()
    if not rooms:
        print("No rooms found, run app.py once first to seed room data.")
        conn.close()
        return

    # 2. Wipe ALL existing bookings so we start from a clean, non-duplicated state
    c.execute("DELETE FROM bookings")
    conn.commit()

    # 3. Pick a random number of rooms to book (11-15), each room booked ONCE,
    #    by a different random student, at a different random time slot.
    num_rooms_to_book = random.randint(11, 15)
    chosen_rooms = random.sample(list(rooms), num_rooms_to_book)
    chosen_students = random.sample(user_ids, min(num_rooms_to_book, len(user_ids)))
    chosen_slots = random.sample(TIME_SLOTS, min(num_rooms_to_book, len(TIME_SLOTS)))

    now = datetime.now()
    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)

    inserted = 0
    for room, (user_id, user_name), slot in zip(chosen_rooms, chosen_students, chosen_slots):
        if slot[0] == "now":
            _, offset_min, duration_min = slot
            start_time = (now + timedelta(minutes=offset_min)).strftime("%Y-%m-%d %H:%M")
            end_time = (now + timedelta(minutes=offset_min + duration_min)).strftime("%Y-%m-%d %H:%M")
        else:
            day_offset, hour, minute, duration_min = slot
            start = today_9am + timedelta(days=day_offset, hours=hour - 9, minutes=minute)
            end = start + timedelta(minutes=duration_min)
            start_time = start.strftime("%Y-%m-%d %H:%M")
            end_time = end.strftime("%Y-%m-%d %H:%M")

        c.execute("""
            INSERT INTO bookings (room_id, user_id, booked_by, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        """, (room["id"], user_id, user_name, start_time, end_time))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"Total demo students: {len(user_ids)}")
    print(f"Booked {inserted} unique rooms out of {len(rooms)} total (target was {num_rooms_to_book}).")
    print("Each booked room has exactly one booking, by a different student.")
    print("\nDemo login credentials (all use password: password123):")
    for name, email, _ in DEMO_STUDENTS:
        print(f"  {email}")


if __name__ == "__main__":
    seed()
