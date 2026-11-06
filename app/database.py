import sqlite3
import os
import hashlib
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hostel.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table (RBAC)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'warden', 'student', 'staff')),
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Rooms Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE NOT NULL,
        block TEXT NOT NULL,
        floor INTEGER NOT NULL,
        capacity INTEGER NOT NULL DEFAULT 2,
        occupied_count INTEGER NOT NULL DEFAULT 0,
        room_type TEXT NOT NULL,
        fee_per_semester REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Full', 'Maintenance'))
    );
    """)

    # Students Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        student_id TEXT UNIQUE NOT NULL,
        room_id INTEGER,
        department TEXT NOT NULL,
        year INTEGER NOT NULL,
        gender TEXT NOT NULL,
        guardian_name TEXT NOT NULL,
        guardian_phone TEXT NOT NULL,
        address TEXT,
        photo_url TEXT,
        id_proof_url TEXT,
        admission_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
    );
    """)

    # Room Allocation Requests (Reallocation / Transfer)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        current_room_id INTEGER,
        requested_room_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_by INTEGER,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (current_room_id) REFERENCES rooms(id),
        FOREIGN KEY (requested_room_id) REFERENCES rooms(id),
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
    );
    """)

    # Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date DATE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Leave')),
        marked_by INTEGER NOT NULL,
        remarks TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, date),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (marked_by) REFERENCES users(id)
    );
    """)

    # Complaints Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Electrical', 'Plumbing', 'Wi-Fi', 'Carpentry', 'Cleanliness', 'Other')),
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Resolved')),
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolution_remarks TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Visitors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        visitor_name TEXT NOT NULL,
        visitor_phone TEXT NOT NULL,
        relation TEXT NOT NULL,
        purpose TEXT NOT NULL,
        time_in TIMESTAMP NOT NULL,
        time_out TIMESTAMP,
        logged_by INTEGER NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (logged_by) REFERENCES users(id)
    );
    """)

    # Fee Management Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        semester TEXT NOT NULL,
        total_amount REAL NOT NULL,
        paid_amount REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL CHECK(status IN ('Paid', 'Pending', 'Partial')),
        due_date DATE NOT NULL,
        payment_date DATE,
        transaction_id TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Announcements Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        target_role TEXT NOT NULL DEFAULT 'all' CHECK(target_role IN ('all', 'student', 'warden', 'staff')),
        posted_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        priority TEXT NOT NULL DEFAULT 'Normal' CHECK(priority IN ('Normal', 'High', 'Urgent')),
        FOREIGN KEY (posted_by) REFERENCES users(id)
    );
    """)

    # Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT DEFAULT '127.0.0.1',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

def seed_sample_data():
    conn = get_db()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Seed Default Users
    users_data = [
        ("admin", hash_password("admin123"), "admin", "Dr. Rajesh Sharma", "admin@hostel.edu", "9876543210"),
        ("warden", hash_password("warden123"), "warden", "Prof. Sunita Verma", "warden@hostel.edu", "9876543211"),
        ("staff", hash_password("staff123"), "staff", "Ramesh Kumar", "staff@hostel.edu", "9876543212"),
        ("HS2026042", hash_password("student123"), "student", "Rahul K.", "rahul.k@student.edu", "9876543213"),
        ("HS2026043", hash_password("student123"), "student", "Sneha P.", "sneha.p@student.edu", "9876543214"),
        ("HS2026044", hash_password("student123"), "student", "Arjun M.", "arjun.m@student.edu", "9876543215"),
        ("HS2026045", hash_password("student123"), "student", "Pooja Roy", "pooja.roy@student.edu", "9876543216"),
        ("HS2026046", hash_password("student123"), "student", "Kavya Menon", "kavya.m@student.edu", "9876543217"),
    ]
    cursor.executemany("""
    INSERT INTO users (username, password_hash, role, full_name, email, phone)
    VALUES (?, ?, ?, ?, ?, ?);
    """, users_data)

    # Seed Rooms (Block A & Block B)
    rooms_data = [
        ("A-101", "Block A", 1, 2, 2, "Double AC", 45000, "Full"),
        ("A-102", "Block A", 1, 2, 1, "Double AC", 45000, "Available"),
        ("A-103", "Block A", 1, 3, 2, "Triple Non-AC", 30000, "Available"),
        ("A-201", "Block A", 2, 1, 0, "Single Deluxe", 60000, "Available"),
        ("A-202", "Block A", 2, 2, 0, "Double Non-AC", 35000, "Available"),
        ("B-101", "Block B", 1, 2, 0, "Double AC", 45000, "Available"),
        ("B-102", "Block B", 1, 3, 0, "Triple Non-AC", 30000, "Available"),
        ("B-201", "Block B", 2, 2, 0, "Double Non-AC", 35000, "Available"),
    ]
    cursor.executemany("""
    INSERT INTO rooms (room_number, block, floor, capacity, occupied_count, room_type, fee_per_semester, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, rooms_data)

    # Fetch User IDs & Room IDs
    cursor.execute("SELECT id, username FROM users WHERE role='student';")
    student_users = {row["username"]: row["id"] for row in cursor.fetchall()}

    cursor.execute("SELECT id, room_number FROM rooms;")
    room_map = {row["room_number"]: row["id"] for row in cursor.fetchall()}

    # Seed Students
    students_data = [
        (student_users["HS2026042"], "HS2026042", room_map["A-101"], "Computer Science", 3, "Male", "K. R. Rao", "9811122334", "Bengaluru, Karnataka", "Active"),
        (student_users["HS2026043"], "HS2026043", room_map["A-101"], "Information Tech", 2, "Female", "P. Suresh", "9811122335", "Mysuru, Karnataka", "Active"),
        (student_users["HS2026044"], "HS2026044", room_map["A-102"], "Electronics Eng", 3, "Male", "M. Narayanan", "9811122336", "Chennai, Tamil Nadu", "Active"),
        (student_users["HS2026045"], "HS2026045", room_map["A-103"], "Mechanical Eng", 1, "Female", "Subhash Roy", "9811122337", "Kolkata, WB", "Active"),
        (student_users["HS2026046"], "HS2026046", room_map["A-103"], "Civil Eng", 2, "Female", "Madhavan M.", "9811122338", "Kochi, Kerala", "Active"),
    ]
    cursor.executemany("""
    INSERT INTO students (user_id, student_id, room_id, department, year, gender, guardian_name, guardian_phone, address, admission_date, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-08-01', ?);
    """, students_data)

    # Fetch Student Table IDs
    cursor.execute("SELECT id, student_id FROM students;")
    student_records = {row["student_id"]: row["id"] for row in cursor.fetchall()}

    # Seed Complaints (Exactly matching Fig 6.2 in SRS!)
    complaints_data = [
        (student_records["HS2026042"], "Fan not working", "Electrical", "Ceiling fan making loud noise and regulator not functioning.", "Pending", "Medium", "2026-08-03 10:15:00"),
        (student_records["HS2026043"], "Water leakage", "Plumbing", "Washroom tap dripping continuously, causing water wastage.", "In Progress", "High", "2026-08-02 14:30:00"),
        (student_records["HS2026044"], "Wi-Fi issue", "Wi-Fi", "Unable to connect to 2nd floor access point from room A-102.", "Resolved", "Low", "2026-08-01 09:00:00"),
        (student_records["HS2026045"], "Study table drawer broken", "Carpentry", "Wooden desk drawer handle is detached.", "Pending", "Low", "2026-08-04 11:20:00"),
    ]
    cursor.executemany("""
    INSERT INTO complaints (student_id, title, category, description, status, priority, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, complaints_data)

    # Seed Attendance (Wardens marking daily)
    today = date.today()
    warden_id = 2
    attendance_records = []
    for day_offset in range(5, -1, -1):
        record_date = (today - timedelta(days=day_offset)).isoformat()
        attendance_records.append((student_records["HS2026042"], record_date, "Present", warden_id, "Biometric verified"))
        attendance_records.append((student_records["HS2026043"], record_date, "Present" if day_offset != 2 else "Leave", warden_id, "Regular" if day_offset != 2 else "Medical leave approved"))
        attendance_records.append((student_records["HS2026044"], record_date, "Present", warden_id, "Regular"))
        attendance_records.append((student_records["HS2026045"], record_date, "Absent" if day_offset == 1 else "Present", warden_id, "Informed late" if day_offset == 1 else "Regular"))
        attendance_records.append((student_records["HS2026046"], record_date, "Present", warden_id, "Regular"))

    cursor.executemany("""
    INSERT INTO attendance (student_id, date, status, marked_by, remarks)
    VALUES (?, ?, ?, ?, ?);
    """, attendance_records)

    # Seed Fees
    fees_data = [
        (student_records["HS2026042"], "Fall 2026", 45000, 45000, "Paid", "2026-08-10", "2026-08-05", "TXN98124012"),
        (student_records["HS2026043"], "Fall 2026", 45000, 0, "Pending", "2026-08-10", None, None),
        (student_records["HS2026044"], "Fall 2026", 45000, 25000, "Partial", "2026-08-10", "2026-08-08", "TXN98124055"),
        (student_records["HS2026045"], "Fall 2026", 30000, 0, "Pending", "2026-08-10", None, None),
        (student_records["HS2026046"], "Fall 2026", 30000, 30000, "Paid", "2026-08-10", "2026-08-04", "TXN98124089"),
    ]
    cursor.executemany("""
    INSERT INTO fees (student_id, semester, total_amount, paid_amount, status, due_date, payment_date, transaction_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, fees_data)

    # Seed Visitors
    visitors_data = [
        (student_records["HS2026042"], "Mr. K. R. Rao", "9811122334", "Father", "Visiting student with study materials", "2026-08-03 16:00:00", "2026-08-03 17:30:00", 3),
        (student_records["HS2026043"], "Mrs. Latha Suresh", "9811122339", "Mother", "Delivering home-cooked snacks", "2026-08-04 11:00:00", "2026-08-04 12:15:00", 3),
        (student_records["HS2026044"], "Vikram Menon", "9811122340", "Cousin", "Academic discussion", "2026-08-04 15:30:00", None, 3),
    ]
    cursor.executemany("""
    INSERT INTO visitors (student_id, visitor_name, visitor_phone, relation, purpose, time_in, time_out, logged_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, visitors_data)

    # Seed Announcements
    announcements_data = [
        ("Hostel Inspection & Cleanliness Drive", "All residents are requested to ensure their rooms are tidy before the monthly inspection on Saturday.", "all", 1, "High"),
        ("Gym & Recreation Room Timings Update", "The indoor sports and gym facilities will now remain open until 10:00 PM on weekdays.", "student", 2, "Normal"),
        ("Mess Committee Meeting", "Hostel floor representatives are invited to attend the mess committee review meeting in Hall A.", "all", 1, "Normal"),
    ]
    cursor.executemany("""
    INSERT INTO announcements (title, content, target_role, posted_by, priority)
    VALUES (?, ?, ?, ?, ?);
    """, announcements_data)

    # Seed Audit Logs
    audit_data = [
        (1, "admin", "SYSTEM_INIT", "Database initialized and initial configuration applied.", "127.0.0.1"),
        (1, "admin", "USER_LOGIN", "Administrator logged into dashboard.", "127.0.0.1"),
        (2, "warden", "ATTENDANCE_MARKED", "Marked daily attendance for Block A and Block B residents.", "127.0.0.1"),
        (4, "HS2026042", "COMPLAINT_RAISED", "Complaint raised: Fan not working in Room A-101.", "127.0.0.1"),
        (1, "admin", "FEE_VERIFIED", "Verified fee transaction TXN98124012 for student HS2026042.", "127.0.0.1"),
    ]
    cursor.executemany("""
    INSERT INTO audit_logs (user_id, username, action, details, ip_address)
    VALUES (?, ?, ?, ?, ?);
    """, audit_data)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_sample_data()
    print("Hostel Database initialized and seeded successfully.")
