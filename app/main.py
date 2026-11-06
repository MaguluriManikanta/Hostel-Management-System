import os
import sqlite3
import csv
import io
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import get_db, hash_password, init_db, seed_sample_data

app = FastAPI(title="Hostel Management System (HMS)", version="2.0.0")

# Add session middleware for simple, cookie-based session state
app.add_middleware(SessionMiddleware, secret_key="hostel-secret-super-key-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Ensure DB is created and seeded on startup
@app.on_event("startup")
def on_startup():
    init_db()
    seed_sample_data()

def log_audit(username: str, action: str, details: str, user_id: Optional[int] = None, ip: str = "127.0.0.1"):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, action, details, ip_address)
            VALUES (?, ?, ?, ?, ?);
        """, (user_id, username, action, details, ip))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit: {e}")

def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# ==================== AUTHENTICATION ROUTES ====================

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    if user:
        if user["role"] == "admin":
            return RedirectResponse(url="/admin/dashboard", status_code=302)
        elif user["role"] == "student":
            return RedirectResponse(url="/student/dashboard", status_code=302)
        elif user["role"] == "warden":
            return RedirectResponse(url="/warden/dashboard", status_code=302)
        elif user["role"] == "staff":
            return RedirectResponse(url="/staff/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": error})

@app.post("/login")
def login_post(
    request: Request,
    role: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    conn = get_db()
    cursor = conn.cursor()
    hashed_pwd = hash_password(password)
    
    cursor.execute("""
        SELECT * FROM users WHERE (username = ? OR email = ?) AND password_hash = ? AND role = ?
    """, (username.strip(), username.strip(), hashed_pwd, role.lower()))
    user = cursor.fetchone()
    conn.close()

    if user:
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        request.session["role"] = user["role"]
        request.session["full_name"] = user["full_name"]

        log_audit(user["username"], "LOGIN_SUCCESS", f"User {user['username']} logged in successfully as {user['role']}", user["id"])

        if user["role"] == "admin":
            return RedirectResponse(url="/admin/dashboard", status_code=302)
        elif user["role"] == "student":
            return RedirectResponse(url="/student/dashboard", status_code=302)
        elif user["role"] == "warden":
            return RedirectResponse(url="/warden/dashboard", status_code=302)
        else:
            return RedirectResponse(url="/staff/dashboard", status_code=302)
    else:
        log_audit(username, "LOGIN_FAILED", f"Failed login attempt with role {role}")
        return templates.TemplateResponse(request=request, name="login.html", context={
            "error": "Invalid User ID, Role or Password. Please try again.",
            "preset_role": role,
            "preset_username": username
        })

@app.get("/logout")
def logout(request: Request):
    username = request.session.get("username", "Guest")
    log_audit(username, "LOGOUT", "User logged out.")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

# ==================== ADMIN DASHBOARD & MODULES ====================

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    # Counts matching UI mockups
    cursor.execute("SELECT COUNT(*) FROM students;")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(occupied_count), SUM(capacity) FROM rooms;")
    occ_row = cursor.fetchone()
    rooms_occupied = occ_row[0] or 0
    total_capacity = occ_row[1] or 0

    cursor.execute("SELECT COUNT(*) FROM fees WHERE status = 'Pending';")
    fees_pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status != 'Resolved';")
    total_complaints = cursor.fetchone()[0]

    # Recent Complaints (Fig 6.2 mockup)
    cursor.execute("""
        SELECT c.id, u.full_name as student_name, c.title as issue, c.category, c.status, c.created_at
        FROM complaints c
        JOIN students s ON c.student_id = s.id
        JOIN users u ON s.user_id = u.id
        ORDER BY c.created_at DESC LIMIT 5;
    """)
    recent_complaints = cursor.fetchall()

    # Recent Announcements
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3;")
    announcements = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(request=request, name="admin_dashboard.html", context={
        "user": user,
        "active_page": "dashboard",
        "total_students": total_students,
        "rooms_occupied": f"{rooms_occupied} / {total_capacity}",
        "fees_pending": fees_pending,
        "complaints_count": total_complaints,
        "recent_complaints": recent_complaints,
        "announcements": announcements
    })

# --- Admin: Students Management (FR-1) ---
@app.get("/admin/students", response_class=HTMLResponse)
def admin_students(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.student_id, u.full_name, u.email, u.phone, s.department, s.year,
               s.gender, s.guardian_name, s.guardian_phone, r.room_number, s.status, s.admission_date
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN rooms r ON s.room_id = r.id
        ORDER BY s.id DESC;
    """)
    students = cursor.fetchall()

    cursor.execute("SELECT * FROM rooms WHERE status = 'Available';")
    available_rooms = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_students.html", context={
        "user": user,
        "active_page": "students",
        "students": students,
        "available_rooms": available_rooms
    })

@app.post("/admin/students/register")
async def register_student(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    department: str = Form(...),
    year: int = Form(...),
    gender: str = Form(...),
    guardian_name: str = Form(...),
    guardian_phone: str = Form(...),
    address: str = Form(...),
    room_id: Optional[int] = Form(None),
    photo: Optional[UploadFile] = File(None)
):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    # Generate Student ID: HS + Current Year + Auto increment number
    cursor.execute("SELECT COUNT(*) FROM students;")
    count = cursor.fetchone()[0] + 43
    student_code = f"HS2026{count:03d}"

    # Create User account
    pwd_hash = hash_password("student123")
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, full_name, email, phone)
        VALUES (?, ?, 'student', ?, ?, ?);
    """, (student_code, pwd_hash, full_name, email, phone))
    new_user_id = cursor.lastrowid

    # Handle photo upload
    photo_path = None
    if photo and photo.filename:
        photo_filename = f"{student_code}_{photo.filename}"
        dest_path = os.path.join(UPLOADS_DIR, photo_filename)
        contents = await photo.read()
        with open(dest_path, "wb") as f:
            f.write(contents)
        photo_path = f"/static/uploads/{photo_filename}"

    # Insert Student record
    cursor.execute("""
        INSERT INTO students (user_id, student_id, room_id, department, year, gender, guardian_name, guardian_phone, address, photo_url, admission_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'), 'Active');
    """, (new_user_id, student_code, room_id, department, year, gender, guardian_name, guardian_phone, address, photo_path))
    new_student_id = cursor.lastrowid

    # If room allocated, update room occupancy
    if room_id:
        cursor.execute("UPDATE rooms SET occupied_count = occupied_count + 1 WHERE id = ?", (room_id,))
        cursor.execute("UPDATE rooms SET status = 'Full' WHERE id = ? AND occupied_count >= capacity", (room_id,))

    # Create Initial Fee record
    cursor.execute("""
        INSERT INTO fees (student_id, semester, total_amount, paid_amount, status, due_date)
        VALUES (?, 'Fall 2026', 45000, 0, 'Pending', date('now', '+30 days'));
    """, (new_student_id,))

    conn.commit()
    conn.close()

    log_audit(user["username"], "STUDENT_REGISTERED", f"Registered new student {student_code} ({full_name})", user["id"])
    return RedirectResponse(url="/admin/students", status_code=302)

# --- Admin: Room Allocation (FR-2) ---
@app.get("/admin/rooms", response_class=HTMLResponse)
def admin_rooms(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, 
               (SELECT COUNT(*) FROM students s WHERE s.room_id = r.id) as actual_occupants
        FROM rooms r
        ORDER BY r.block, r.room_number;
    """)
    rooms = cursor.fetchall()

    # Room transfer requests
    cursor.execute("""
        SELECT rr.id, s.student_id, u.full_name, r1.room_number as current_room,
               r2.room_number as requested_room, rr.reason, rr.status, rr.created_at
        FROM room_requests rr
        JOIN students s ON rr.student_id = s.id
        JOIN users u ON s.user_id = u.id
        LEFT JOIN rooms r1 ON rr.current_room_id = r1.id
        JOIN rooms r2 ON rr.requested_room_id = r2.id
        ORDER BY rr.created_at DESC;
    """)
    requests = cursor.fetchall()

    # Unallocated students
    cursor.execute("""
        SELECT s.id, s.student_id, u.full_name, s.department
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.room_id IS NULL;
    """)
    unallocated = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(request=request, name="admin_rooms.html", context={
        "user": user,
        "active_page": "rooms",
        "rooms": rooms,
        "requests": requests,
        "unallocated": unallocated
    })

@app.post("/admin/rooms/create")
def create_room(
    request: Request,
    room_number: str = Form(...),
    block: str = Form(...),
    floor: int = Form(...),
    capacity: int = Form(...),
    room_type: str = Form(...),
    fee_per_semester: float = Form(...)
):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO rooms (room_number, block, floor, capacity, occupied_count, room_type, fee_per_semester, status)
            VALUES (?, ?, ?, ?, 0, ?, ?, 'Available');
        """, (room_number, block, floor, capacity, room_type, fee_per_semester))
        conn.commit()
        log_audit(user["username"], "ROOM_CREATED", f"Created room {room_number} in {block}", user["id"])
    except Exception as e:
        print(f"Error creating room: {e}")
    finally:
        conn.close()
    return RedirectResponse(url="/admin/rooms", status_code=302)

@app.post("/admin/rooms/allocate")
def allocate_room(request: Request, student_id: int = Form(...), room_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    # Check capacity constraint (FR-2.3)
    cursor.execute("SELECT capacity, occupied_count FROM rooms WHERE id = ?", (room_id,))
    room = cursor.fetchone()
    if not room or room["occupied_count"] >= room["capacity"]:
        conn.close()
        return RedirectResponse(url="/admin/rooms?error=RoomCapacityExceeded", status_code=302)

    cursor.execute("UPDATE students SET room_id = ? WHERE id = ?", (room_id, student_id))
    cursor.execute("UPDATE rooms SET occupied_count = occupied_count + 1 WHERE id = ?", (room_id,))
    cursor.execute("UPDATE rooms SET status = 'Full' WHERE id = ? AND occupied_count >= capacity", (room_id,))

    conn.commit()
    conn.close()
    log_audit(user["username"], "ROOM_ALLOCATED", f"Allocated room ID {room_id} to student ID {student_id}", user["id"])
    return RedirectResponse(url="/admin/rooms", status_code=302)

@app.post("/admin/rooms/request/update")
def update_room_request(request: Request, request_id: int = Form(...), action: str = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    if action == "approve":
        cursor.execute("SELECT student_id, current_room_id, requested_room_id FROM room_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        if req:
            # Check capacity
            cursor.execute("SELECT capacity, occupied_count FROM rooms WHERE id = ?", (req["requested_room_id"],))
            target_room = cursor.fetchone()
            if target_room and target_room["occupied_count"] < target_room["capacity"]:
                # Free current room
                if req["current_room_id"]:
                    cursor.execute("UPDATE rooms SET occupied_count = MAX(0, occupied_count - 1), status = 'Available' WHERE id = ?", (req["current_room_id"],))
                # Allocate new room
                cursor.execute("UPDATE students SET room_id = ? WHERE id = ?", (req["requested_room_id"], req["student_id"]))
                cursor.execute("UPDATE rooms SET occupied_count = occupied_count + 1 WHERE id = ?", (req["requested_room_id"],))
                cursor.execute("UPDATE rooms SET status = 'Full' WHERE id = ? AND occupied_count >= capacity", (req["requested_room_id"],))
                cursor.execute("UPDATE room_requests SET status = 'Approved', reviewed_by = ? WHERE id = ?", (user["id"], request_id))
    else:
        cursor.execute("UPDATE room_requests SET status = 'Rejected', reviewed_by = ? WHERE id = ?", (user["id"], request_id))

    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/rooms", status_code=302)

# --- Admin: Fee Management (FR-9) ---
@app.get("/admin/fees", response_class=HTMLResponse)
def admin_fees(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, s.student_id, u.full_name, r.room_number
        FROM fees f
        JOIN students s ON f.student_id = s.id
        JOIN users u ON s.user_id = u.id
        LEFT JOIN rooms r ON s.room_id = r.id
        ORDER BY f.id DESC;
    """)
    fees = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_fees.html", context={
        "user": user,
        "active_page": "fees",
        "fees": fees
    })

# --- Admin: Attendance Management (FR-4) ---
@app.get("/admin/attendance", response_class=HTMLResponse)
def admin_attendance(request: Request, selected_date: Optional[str] = None):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    today_str = selected_date or date.today().isoformat()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id as student_db_id, s.student_id, u.full_name, r.room_number,
               a.status as attendance_status, a.remarks
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN rooms r ON s.room_id = r.id
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
        ORDER BY r.room_number, s.student_id;
    """, (today_str,))
    records = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_attendance.html", context={
        "user": user,
        "active_page": "attendance",
        "records": records,
        "selected_date": today_str
    })

@app.post("/admin/attendance/mark")
def mark_attendance(
    request: Request,
    student_id: int = Form(...),
    att_date: str = Form(...),
    status: str = Form(...),
    remarks: Optional[str] = Form("")
):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (student_id, date, status, marked_by, remarks)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(student_id, date) DO UPDATE SET
            status = excluded.status,
            marked_by = excluded.marked_by,
            remarks = excluded.remarks,
            timestamp = CURRENT_TIMESTAMP;
    """, (student_id, att_date, status, user["id"], remarks))
    conn.commit()
    conn.close()

    log_audit(user["username"], "ATTENDANCE_MARKED", f"Marked {status} for student ID {student_id} on {att_date}", user["id"])
    return RedirectResponse(url=f"/admin/attendance?selected_date={att_date}", status_code=302)

# --- Admin: Complaints & Maintenance (FR-6) ---
@app.get("/admin/complaints", response_class=HTMLResponse)
def admin_complaints(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, s.student_id, u.full_name, r.room_number
        FROM complaints c
        JOIN students s ON c.student_id = s.id
        JOIN users u ON s.user_id = u.id
        LEFT JOIN rooms r ON s.room_id = r.id
        ORDER BY c.created_at DESC;
    """)
    complaints = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_complaints.html", context={
        "user": user,
        "active_page": "complaints",
        "complaints": complaints
    })

@app.post("/admin/complaints/update")
def update_complaint(
    request: Request,
    complaint_id: int = Form(...),
    status: str = Form(...),
    resolution_remarks: Optional[str] = Form("")
):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE complaints
        SET status = ?, resolution_remarks = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?;
    """, (status, resolution_remarks, complaint_id))
    conn.commit()
    conn.close()

    log_audit(user["username"], "COMPLAINT_UPDATED", f"Updated complaint #{complaint_id} to {status}", user["id"])
    return RedirectResponse(url="/admin/complaints", status_code=302)

# --- Admin: Visitor Log (FR-5) ---
@app.get("/admin/visitors", response_class=HTMLResponse)
def admin_visitors(request: Request, search: Optional[str] = None):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    if search:
        search_query = f"%{search.strip()}%"
        cursor.execute("""
            SELECT v.*, s.student_id, u.full_name as student_name, r.room_number
            FROM visitors v
            JOIN students s ON v.student_id = s.id
            JOIN users u ON s.user_id = u.id
            LEFT JOIN rooms r ON s.room_id = r.id
            WHERE v.visitor_name LIKE ? OR s.student_id LIKE ? OR u.full_name LIKE ?
            ORDER BY v.time_in DESC;
        """, (search_query, search_query, search_query))
    else:
        cursor.execute("""
            SELECT v.*, s.student_id, u.full_name as student_name, r.room_number
            FROM visitors v
            JOIN students s ON v.student_id = s.id
            JOIN users u ON s.user_id = u.id
            LEFT JOIN rooms r ON s.room_id = r.id
            ORDER BY v.time_in DESC;
        """)
    visitors = cursor.fetchall()

    cursor.execute("""
        SELECT s.id, s.student_id, u.full_name FROM students s JOIN users u ON s.user_id = u.id;
    """)
    students = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_visitors.html", context={
        "user": user,
        "active_page": "visitors",
        "visitors": visitors,
        "students": students,
        "search_term": search or ""
    })

@app.post("/admin/visitors/add")
def add_visitor(
    request: Request,
    student_id: int = Form(...),
    visitor_name: str = Form(...),
    visitor_phone: str = Form(...),
    relation: str = Form(...),
    purpose: str = Form(...)
):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO visitors (student_id, visitor_name, visitor_phone, relation, purpose, time_in, logged_by)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?);
    """, (student_id, visitor_name, visitor_phone, relation, purpose, user["id"]))
    conn.commit()
    conn.close()

    log_audit(user["username"], "VISITOR_LOGGED", f"Logged visitor {visitor_name} for student ID {student_id}", user["id"])
    return RedirectResponse(url="/admin/visitors", status_code=302)

@app.post("/admin/visitors/checkout")
def checkout_visitor(request: Request, visitor_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden", "staff"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE visitors SET time_out = datetime('now') WHERE id = ?", (visitor_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/visitors", status_code=302)

# --- Admin: Reports (FR-9) ---
@app.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    # Room statistics
    cursor.execute("SELECT block, COUNT(*) as total_rooms, SUM(capacity) as capacity, SUM(occupied_count) as occupied FROM rooms GROUP BY block;")
    room_stats = cursor.fetchall()

    # Fee statistics
    cursor.execute("SELECT status, COUNT(*) as count, SUM(total_amount) as total_val, SUM(paid_amount) as collected_val FROM fees GROUP BY status;")
    fee_stats = cursor.fetchall()

    # Complaint statistics
    cursor.execute("SELECT category, COUNT(*) as count FROM complaints GROUP BY category;")
    complaint_stats = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(request=request, name="admin_reports.html", context={
        "user": user,
        "active_page": "reports",
        "room_stats": room_stats,
        "fee_stats": fee_stats,
        "complaint_stats": complaint_stats
    })

@app.get("/admin/reports/export/{report_type}")
def export_report_csv(request: Request, report_type: str):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "occupancy":
        writer.writerow(["Room Number", "Block", "Floor", "Capacity", "Occupied", "Status", "Fee Per Semester"])
        cursor.execute("SELECT room_number, block, floor, capacity, occupied_count, status, fee_per_semester FROM rooms;")
        for row in cursor.fetchall():
            writer.writerow(list(row))
        filename = "room_occupancy_report.csv"

    elif report_type == "fees":
        writer.writerow(["Student ID", "Student Name", "Semester", "Total Amount", "Paid Amount", "Status", "Due Date", "Transaction ID"])
        cursor.execute("""
            SELECT s.student_id, u.full_name, f.semester, f.total_amount, f.paid_amount, f.status, f.due_date, f.transaction_id
            FROM fees f JOIN students s ON f.student_id = s.id JOIN users u ON s.user_id = u.id;
        """)
        for row in cursor.fetchall():
            writer.writerow(list(row))
        filename = "fee_collection_report.csv"

    elif report_type == "attendance":
        writer.writerow(["Date", "Student ID", "Student Name", "Status", "Remarks"])
        cursor.execute("""
            SELECT a.date, s.student_id, u.full_name, a.status, a.remarks
            FROM attendance a JOIN students s ON a.student_id = s.id JOIN users u ON s.user_id = u.id
            ORDER BY a.date DESC;
        """)
        for row in cursor.fetchall():
            writer.writerow(list(row))
        filename = "attendance_summary_report.csv"
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid report type")

    conn.close()
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- Admin: Announcements Broadcast (FR-7) ---
@app.post("/admin/announcements/broadcast")
def broadcast_announcement(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    target_role: str = Form("all"),
    priority: str = Form("Normal")
):
    user = get_current_user(request)
    if not user or user["role"] not in ["admin", "warden"]:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO announcements (title, content, target_role, posted_by, priority)
        VALUES (?, ?, ?, ?, ?);
    """, (title, content, target_role, user["id"], priority))
    conn.commit()
    conn.close()

    log_audit(user["username"], "ANNOUNCEMENT_BROADCAST", f"Broadcasted announcement: {title}", user["id"])
    return RedirectResponse(url="/admin/dashboard", status_code=302)

# --- Admin: Audit Logs (FR-8.3) ---
@app.get("/admin/audit-logs", response_class=HTMLResponse)
def admin_audit_logs(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100;")
    logs = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin_audit.html", context={
        "user": user,
        "active_page": "audit",
        "logs": logs
    })

# ==================== STUDENT DASHBOARD & PORTAL ====================

@app.get("/student/dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()

    # Student details with room
    cursor.execute("""
        SELECT s.*, r.room_number, r.block, r.floor, r.room_type, r.fee_per_semester
        FROM students s
        LEFT JOIN rooms r ON s.room_id = r.id
        WHERE s.user_id = ?;
    """, (user["id"],))
    student = cursor.fetchone()

    # Personal Attendance
    cursor.execute("""
        SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC LIMIT 10;
    """, (student["id"],))
    attendance_records = cursor.fetchall()

    # Attendance percentage
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?;", (student["id"],))
    total_att = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND status = 'Present';", (student["id"],))
    present_att = cursor.fetchone()[0]
    att_percent = round((present_att / total_att * 100), 1) if total_att > 0 else 100.0

    # Personal Complaints
    cursor.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC;", (student["id"],))
    complaints = cursor.fetchall()

    # Personal Fee Status
    cursor.execute("SELECT * FROM fees WHERE student_id = ? ORDER BY id DESC;", (student["id"],))
    fees = cursor.fetchall()

    # Announcements
    cursor.execute("SELECT * FROM announcements WHERE target_role IN ('all', 'student') ORDER BY created_at DESC LIMIT 5;")
    announcements = cursor.fetchall()

    # Available rooms for transfer
    cursor.execute("SELECT * FROM rooms WHERE status = 'Available';")
    available_rooms = cursor.fetchall()

    # Student's pending room transfer requests
    cursor.execute("""
        SELECT rr.*, r.room_number as requested_room_number
        FROM room_requests rr
        JOIN rooms r ON rr.requested_room_id = r.id
        WHERE rr.student_id = ? ORDER BY rr.created_at DESC;
    """, (student["id"],))
    transfer_requests = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(request=request, name="student_dashboard.html", context={
        "user": user,
        "student": student,
        "attendance_records": attendance_records,
        "attendance_percent": att_percent,
        "complaints": complaints,
        "fees": fees,
        "announcements": announcements,
        "available_rooms": available_rooms,
        "transfer_requests": transfer_requests
    })

@app.post("/student/complaint/submit")
def student_submit_complaint(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    priority: str = Form("Medium")
):
    user = get_current_user(request)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (user["id"],))
    student = cursor.fetchone()

    cursor.execute("""
        INSERT INTO complaints (student_id, title, category, description, priority, status)
        VALUES (?, ?, ?, ?, ?, 'Pending');
    """, (student["id"], title, category, description, priority))
    conn.commit()
    conn.close()

    log_audit(user["username"], "COMPLAINT_FILED", f"Student filed complaint: {title}", user["id"])
    return RedirectResponse(url="/student/dashboard#complaints", status_code=302)

@app.post("/student/room/request")
def student_request_room_transfer(
    request: Request,
    requested_room_id: int = Form(...),
    reason: str = Form(...)
):
    user = get_current_user(request)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, room_id FROM students WHERE user_id = ?", (user["id"],))
    student = cursor.fetchone()

    cursor.execute("""
        INSERT INTO room_requests (student_id, current_room_id, requested_room_id, reason, status)
        VALUES (?, ?, ?, ?, 'Pending');
    """, (student["id"], student["room_id"], requested_room_id, reason))
    conn.commit()
    conn.close()

    log_audit(user["username"], "TRANSFER_REQUEST", f"Student requested transfer to room ID {requested_room_id}", user["id"])
    return RedirectResponse(url="/student/dashboard#room-transfer", status_code=302)

@app.post("/student/fee/pay")
def student_pay_fee(request: Request, fee_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor()
    txn_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}"

    cursor.execute("""
        UPDATE fees
        SET status = 'Paid', paid_amount = total_amount, payment_date = date('now'), transaction_id = ?
        WHERE id = ?;
    """, (txn_id, fee_id))
    conn.commit()
    conn.close()

    log_audit(user["username"], "FEE_PAID", f"Student paid fee #{fee_id} with TXN {txn_id}", user["id"])
    return RedirectResponse(url="/student/dashboard#fees", status_code=302)

# ==================== WARDEN & STAFF DASHBOARDS ====================

@app.get("/warden/dashboard", response_class=HTMLResponse)
def warden_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["warden", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/admin/attendance", status_code=302)

@app.get("/staff/dashboard", response_class=HTMLResponse)
def staff_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["staff", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/admin/visitors", status_code=302)
