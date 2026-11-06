-- Hostel Management System (HMS) - Relational Database Schema
-- DBMS: SQLite 3 / Relational DBMS Compatible

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

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT DEFAULT '127.0.0.1',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
